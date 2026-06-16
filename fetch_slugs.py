# fetch_slugs.py — lấy 10k slug phổ biến nhất qua API
import requests, time, json
from pathlib import Path

API = "https://api.wordpress.org/plugins/info/1.2/"

def fetch_slugs(browse="popular", target=10000):
    slugs, page = [], 1
    while len(slugs) < target:
        r = requests.get(API, params={
            "action": "query_plugins",
            "request[page]": page,
            "request[per_page]": 250,
            "request[browse]": browse,
            "request[fields][sections]": "false",
            "request[fields][description]": "false",
        }, timeout=30)
        data = r.json()
        plugins = data.get("plugins", [])
        if not plugins: break
        slugs.extend(p["slug"] for p in plugins)
        page += 1
        time.sleep(0.3)  # tử tế với api.wordpress.org
    return slugs[:target]

if __name__ == "__main__":
    all_slugs = set()
    for mode in ["popular", "updated", "new", "top-rated"]:
        all_slugs.update(fetch_slugs(mode, 5000))
    Path("slugs.txt").write_text("\n".join(sorted(all_slugs)))
