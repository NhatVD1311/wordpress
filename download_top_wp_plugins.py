"""
Script: download_top_wp_plugins.py  (optimized)
Mục đích: Tải plugin WordPress phổ biến phục vụ nghiên cứu bảo mật.

Cải tiến so với bản gốc:
  - per_page 10 -> 250  (giảm ~25x số lần gọi API)
  - Download song song qua ThreadPoolExecutor (mặc định 20 workers)
  - Sửa bug timezone (naive vs aware datetime gây TypeError)
  - Cache os.listdir() 1 lần thay vì gọi mỗi plugin
  - Session có Retry + exponential backoff (chịu được API flap)
  - Kiểm tra integrity của ZIP trước khi extract
  - Streaming download (không nuốt RAM với plugin lớn)
  - Tách rõ thư mục zips/ và unzipped/
  - Cấu hình được browse mode, output dir, max plugins
  - Bắt KeyboardInterrupt sạch sẽ, không bare except

Usage:
  python download_top_wp_plugins.py                       # mặc định: 100k+ installs, 2 năm
  python download_top_wp_plugins.py -i 50000 -u 3 -w 30
  python download_top_wp_plugins.py --max-plugins 1000 -o ./corpus
"""

import argparse
import atexit
import os
import shutil
import sys
import tempfile
import time
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api.wordpress.org/plugins/info/1.2/"


def resolve_ca_bundle(user_ca: str | None, insecure: bool):
    """
    Trả về giá trị cho `session.verify`:
      - False  nếu --insecure (TẮT verify, chỉ dùng khi debug)
      - đường dẫn tới file bundle đã gộp (certifi + corporate CA) nếu user_ca có
      - True (dùng default certifi) nếu không có gì

    Logic gộp: corporate proxy (Zscaler, Netskope, Bluecoat, Palo Alto, v.v.)
    re-sign mọi cert outbound bằng CA nội bộ. Chỉ đưa intermediate_certs.crt
    cho `verify=` sẽ fail với các host KHÔNG bị MITM. Gộp với certifi đảm bảo
    cả 2 trường hợp đều hoạt động.
    """
    if insecure:
        warnings.warn("SSL verification DISABLED — không dùng trong production.")
        # Tắt cảnh báo InsecureRequestWarning để log đỡ ồn
        from urllib3.exceptions import InsecureRequestWarning
        warnings.simplefilter("ignore", InsecureRequestWarning)
        return False

    # Ưu tiên: arg dòng lệnh > env REQUESTS_CA_BUNDLE > env SSL_CERT_FILE
    ca_path = user_ca or os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")
    if not ca_path:
        return True  # default certifi

    ca_path = Path(ca_path)
    if not ca_path.is_file():
        sys.exit(f"[!] CA bundle không tồn tại: {ca_path}")

    # Gộp certifi bundle với corporate CA vào 1 file tạm
    try:
        import certifi
        certifi_path = Path(certifi.where())
    except ImportError:
        sys.exit("[!] Thiếu module `certifi`. Cài: pip install certifi")

    tmp = tempfile.NamedTemporaryFile(
        mode="wb", suffix="-ca-bundle.crt", delete=False
    )
    tmp.write(certifi_path.read_bytes())
    tmp.write(b"\n")
    tmp.write(ca_path.read_bytes())
    tmp.close()
    atexit.register(lambda: os.unlink(tmp.name) if os.path.exists(tmp.name) else None)

    print(f"[*] CA bundle: certifi ({certifi_path.name}) + {ca_path.name} -> {tmp.name}")
    return tmp.name


def make_session(verify=True) -> requests.Session:
    """HTTP session có retry + backoff + connection pool."""
    s = requests.Session()
    s.verify = verify
    retry = Retry(
        total=5,
        backoff_factor=1.0,                       # 1s, 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=50,
        pool_maxsize=50,
    )
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": "wp-plugin-research/1.0"})
    return s


def fetch_page(session, page, per_page=250, browse="popular"):
    """Lấy 1 trang plugin từ API. Raise nếu lỗi (Retry đã handle các lỗi tạm)."""
    params = {
        "action": "query_plugins",
        "request[page]": page,
        "request[per_page]": per_page,
        "request[browse]": browse,
        # Bỏ các field nặng không dùng để giảm payload
        "request[fields][sections]": "false",
        "request[fields][description]": "false",
        "request[fields][short_description]": "false",
        "request[fields][screenshots]": "false",
        "request[fields][icons]": "false",
        "request[fields][banners]": "false",
        "request[fields][contributors]": "false",
        "request[fields][ratings]": "false",
    }
    r = session.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("plugins", [])


def parse_last_updated(raw: str) -> datetime:
    """
    'last_updated' của WordPress trả về dạng '2025-08-15 3:30PM GMT'.
    %Z trong strptime hành xử không nhất quán giữa các Python version,
    nên strip token timezone rồi gán UTC thủ công cho an toàn.
    """
    parts = raw.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].isalpha():
        raw = parts[0]
    dt = datetime.strptime(raw, "%Y-%m-%d %I:%M%p")
    return dt.replace(tzinfo=timezone.utc)


def classify(plugin, min_installs, max_age_days, already_have, now):
    """
    Phân loại 1 plugin:
      'stop'  -> đã dưới ngưỡng installs, dừng hẳn (vì kết quả sort giảm dần)
      'have'  -> đã tải version này rồi
      'stale' -> không update đủ gần đây
      None    -> cần download
    """
    if plugin.get("active_installs", 0) < min_installs:
        return "stop"

    version_file = plugin["download_link"].rsplit("/", 1)[-1]
    if version_file in already_have:
        return "have"

    try:
        last_updated = parse_last_updated(plugin["last_updated"])
    except (ValueError, KeyError):
        return "stale"

    if (now - last_updated).days > max_age_days:
        return "stale"

    return None


def download_one(session, plugin, zip_dir: Path, unzip_dir: Path):
    """Tải + unzip 1 plugin. Trả về (slug, status)."""
    slug = plugin["slug"]
    url = plugin["download_link"]
    version_file = url.rsplit("/", 1)[-1]
    dest = zip_dir / version_file

    try:
        # Xóa version cũ của cùng plugin (giữ corpus gọn, chỉ 1 version/plugin)
        for f in zip_dir.glob(f"{slug}.*.zip"):
            if f.name != version_file:
                f.unlink(missing_ok=True)

        # Streaming download
        with session.get(url, timeout=120, stream=True) as r:
            r.raise_for_status()
            with open(dest, "wb") as fp:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        fp.write(chunk)

        # Verify ZIP — bắt được file truncated hoặc HTML lỗi
        if not zipfile.is_zipfile(dest):
            dest.unlink(missing_ok=True)
            return slug, "bad_zip"

        # Extract lại từ đầu: xóa folder cũ để không lẫn file của version cũ
        target = unzip_dir / slug
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

        with zipfile.ZipFile(dest, "r") as z:
            z.extractall(unzip_dir)

        return slug, "ok"
    except Exception as e:
        dest.unlink(missing_ok=True)
        return slug, f"error: {type(e).__name__}: {e}"


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Bulk-download WordPress plugins for security research.",
    )
    parser.add_argument("-i", "--active-installs", type=int, default=100_000,
                        help="Ngưỡng tối thiểu active installs")
    parser.add_argument("-u", "--years-since-update", type=int, default=2,
                        choices=range(1, 11),
                        help="Chỉ tải plugin update trong X năm gần nhất")
    parser.add_argument("-p", "--per-page", type=int, default=250,
                        help="Số plugin mỗi trang API (max ~250)")
    parser.add_argument("-w", "--workers", type=int, default=20,
                        help="Số luồng download song song")
    parser.add_argument("-b", "--browse", default="popular",
                        choices=["popular", "updated", "new", "top-rated"])
    parser.add_argument("-o", "--output-dir", default=".",
                        help="Thư mục lưu zips/ và unzipped/")
    parser.add_argument("--max-plugins", type=int, default=None,
                        help="Hard cap tổng số plugin tải về")
    parser.add_argument("--sleep", type=float, default=0.3,
                        help="Sleep giữa các trang API (giây)")
    parser.add_argument("--ca-bundle", default=None,
                        help="Đường dẫn tới file CA cert (PEM) cho corporate "
                             "SSL inspection. Mặc định đọc env REQUESTS_CA_BUNDLE.")
    parser.add_argument("--insecure", action="store_true",
                        help="TẮT SSL verification (chỉ dùng để debug).")
    args = parser.parse_args()

    verify = resolve_ca_bundle(args.ca_bundle, args.insecure)

    out = Path(args.output_dir).resolve()
    zip_dir = out / "zips"
    unzip_dir = out / "unzipped"
    zip_dir.mkdir(parents=True, exist_ok=True)
    unzip_dir.mkdir(parents=True, exist_ok=True)

    max_age_days = args.years_since_update * 365
    already_have = {f.name for f in zip_dir.glob("*.zip")}

    print(f"[*] Threshold: ≥{args.active_installs:,} installs, "
          f"updated ≤{args.years_since_update}y, browse={args.browse}")
    print(f"[*] Output: {out}  (đã có {len(already_have)} zips)")
    print(f"[*] Workers: {args.workers}, per_page: {args.per_page}")

    session = make_session(verify=verify)
    downloaded = failed = 0
    stop = False
    page = 1

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while not stop:
            now = datetime.now(timezone.utc)
            try:
                plugins = fetch_page(session, page, args.per_page, args.browse)
            except Exception as e:
                print(f"[!] Page {page} fetch failed sau retry: {e}")
                break

            if not plugins:
                print(f"[*] Page {page} rỗng — hết dữ liệu.")
                break

            to_download = []
            for p in plugins:
                action = classify(p, args.active_installs, max_age_days,
                                  already_have, now)
                if action == "stop":
                    print(f"[*] Tới ngưỡng installs tại {p['slug']} "
                          f"({p['active_installs']:,}). Dừng.")
                    stop = True
                    break
                if action is None:
                    to_download.append(p)

            if to_download:
                futs = {pool.submit(download_one, session, p, zip_dir, unzip_dir):
                        p["slug"] for p in to_download}
                for fut in as_completed(futs):
                    slug, status = fut.result()
                    if status == "ok":
                        downloaded += 1
                        print(f"  ✓ {slug}")
                    else:
                        failed += 1
                        print(f"  ✗ {slug}: {status}")
                    if args.max_plugins and downloaded >= args.max_plugins:
                        print(f"[*] Đạt max-plugins={args.max_plugins}, dừng.")
                        stop = True
                        break

            print(f"[page {page}] downloaded={downloaded} failed={failed} "
                  f"page_size={len(plugins)}")
            page += 1
            if not stop:
                time.sleep(args.sleep)

    print(f"\n[done] downloaded={downloaded} failed={failed}")
    print(f"[done] zips:     {zip_dir}")
    print(f"[done] unzipped: {unzip_dir}")
    print(f"\nBước tiếp: semgrep --config rules/ --json -o findings.json {unzip_dir}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Bị ngắt bởi người dùng, thoát sạch.")
        sys.exit(130)