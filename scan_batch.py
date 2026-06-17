"""
scan_batch.py — Quét Semgrep từng plugin riêng lẻ, có resume + tuning cho máy yếu.

Tại sao per-plugin thay vì gộp:
  - RAM reset sau mỗi plugin (tránh tích lũy memory)
  - Treo 1 plugin không kéo cả batch xuống
  - Resume được sau Ctrl+C / OOM / mất điện
  - Có thể chạy --jobs 1 mà vẫn nhanh (vì plugin nhỏ)

Trade-off: overhead khởi động Semgrep ~3-5s/plugin. Với 100 plugin = ~5-8 phút
overhead. Chấp nhận được, đổi lại không bị treo máy.

Usage:
  python scan_batch.py --corpus ./corpus/unzipped/ --rules ./rules/ --limit 100
  python scan_batch.py --corpus ./corpus/unzipped/ --rules ./rules/  # full
  # Bị ngắt? Chạy lại — tự skip cái đã scan
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def scan_one(plugin_dir: Path, rules_dir: Path, out_file: Path,
             timeout_total: int, jobs: int, max_bytes: int):
    """Chạy semgrep cho 1 plugin. Trả về (ok, message)."""
    cmd = [
        "semgrep",
        "--config", str(rules_dir),
        "--json",
        "--output", str(out_file),
        "--jobs", str(jobs),
        "--max-target-bytes", str(max_bytes),
        "--timeout", "10",                # per rule per file
        "--timeout-threshold", "3",       # skip file sau 3 lần timeout rule
        "--no-rewrite-rule-ids",
        "--metrics", "off",
        "--disable-version-check",
        "--quiet",
        str(plugin_dir),
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_total,
        )
        if res.returncode in (0, 1):  # 0=clean, 1=findings
            return True, "ok"
        return False, f"exit {res.returncode}: {res.stderr.strip()[:200]}"
    except subprocess.TimeoutExpired:
        return False, f"timeout > {timeout_total}s"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def merge_findings(per_plugin_dir: Path, merged_out: Path):
    """Gộp tất cả {slug}.json thành 1 findings.json hợp lệ cho triage.py."""
    all_results = []
    errors = 0
    for f in per_plugin_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            all_results.extend(data.get("results", []))
        except Exception as e:
            errors += 1
            print(f"  [!] {f.name}: parse error {e}")
    merged = {"version": "merged", "results": all_results, "errors": []}
    merged_out.write_text(json.dumps(merged))
    return len(all_results), errors


def main():
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--corpus", required=True, help="Thư mục unzipped/")
    p.add_argument("--rules", required=True, help="Thư mục rules/")
    p.add_argument("--out-dir", default="./scan_out",
                   help="Lưu findings từng plugin + merged")
    p.add_argument("--limit", type=int, default=None,
                   help="Chỉ scan N plugin đầu (alphabet sort)")
    p.add_argument("--jobs", type=int, default=2,
                   help="Semgrep --jobs. Máy 4GB RAM nên để 1, 8GB+ để 2-4")
    p.add_argument("--timeout-total", type=int, default=300,
                   help="Timeout tổng cho 1 plugin (giây)")
    p.add_argument("--max-bytes", type=int, default=1_000_000,
                   help="Skip file > N bytes (LFI vuln thường file nhỏ)")
    p.add_argument("--force", action="store_true",
                   help="Re-scan cả plugin đã có result (mặc định skip)")
    p.add_argument("--merge-only", action="store_true",
                   help="Chỉ merge findings có sẵn, không scan thêm")
    args = p.parse_args()

    corpus = Path(args.corpus).resolve()
    rules = Path(args.rules).resolve()
    out_dir = Path(args.out_dir).resolve()
    per_plugin = out_dir / "per_plugin"
    failed_log = out_dir / "failed.log"
    merged_file = out_dir / "findings.json"

    per_plugin.mkdir(parents=True, exist_ok=True)

    if args.merge_only:
        n, errs = merge_findings(per_plugin, merged_file)
        print(f"[merge] {n} findings từ {len(list(per_plugin.glob('*.json')))} file "
              f"({errs} parse errors) -> {merged_file}")
        return

    # Liệt kê plugin (sort để resume deterministic)
    all_plugins = sorted(d for d in corpus.iterdir() if d.is_dir())
    if args.limit:
        all_plugins = all_plugins[: args.limit]

    # Skip những plugin đã scan thành công
    done = {f.stem for f in per_plugin.glob("*.json")} if not args.force else set()
    todo = [p for p in all_plugins if p.name not in done]

    print(f"[*] Corpus: {corpus} ({len(all_plugins)} plugin trong scope)")
    print(f"[*] Đã scan: {len(done)} | Còn lại: {len(todo)}")
    print(f"[*] Jobs={args.jobs}, timeout/plugin={args.timeout_total}s, "
          f"max-bytes={args.max_bytes:,}")

    if not todo:
        print("[*] Không có plugin nào cần scan. Merge findings...")
        n, _ = merge_findings(per_plugin, merged_file)
        print(f"[done] {n} findings -> {merged_file}")
        return

    t0 = time.time()
    ok_count = fail_count = 0
    with open(failed_log, "a") as ferr:
        for i, plugin in enumerate(todo, 1):
            out_file = per_plugin / f"{plugin.name}.json"
            t1 = time.time()
            ok, msg = scan_one(
                plugin, rules, out_file,
                timeout_total=args.timeout_total,
                jobs=args.jobs,
                max_bytes=args.max_bytes,
            )
            dt = time.time() - t1

            if ok:
                ok_count += 1
                # Đếm findings để in tiến độ
                try:
                    n_find = len(json.loads(out_file.read_text()).get("results", []))
                except Exception:
                    n_find = "?"
                print(f"  [{i}/{len(todo)}] ✓ {plugin.name} "
                      f"({dt:.1f}s, {n_find} findings)")
            else:
                fail_count += 1
                out_file.unlink(missing_ok=True)
                ferr.write(f"{plugin.name}\t{msg}\n")
                ferr.flush()
                print(f"  [{i}/{len(todo)}] ✗ {plugin.name} ({dt:.1f}s): {msg}")

    elapsed = time.time() - t0
    print(f"\n[done] scan: ok={ok_count} fail={fail_count} ({elapsed/60:.1f} phút)")

    n, errs = merge_findings(per_plugin, merged_file)
    print(f"[done] merged: {n} findings ({errs} parse errors)")
    print(f"[done] file: {merged_file}")
    print(f"[done] failed log: {failed_log}")
    print(f"\nBước tiếp: python triage.py --findings {merged_file} --corpus {corpus}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Interrupted. Chạy lại lệnh để resume.")
        sys.exit(130)