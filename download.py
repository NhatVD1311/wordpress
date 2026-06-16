# download.py
import asyncio, aiohttp, aiofiles
from pathlib import Path

OUT = Path("plugins_zip"); OUT.mkdir(exist_ok=True)
SEM = asyncio.Semaphore(20)  # 20 concurrent là vừa

async def grab(session, slug):
    async with SEM:
        url = f"https://downloads.wordpress.org/plugin/{slug}.zip"
        dest = OUT / f"{slug}.zip"
        if dest.exists(): return
        try:
            async with session.get(url, timeout=60) as r:
                if r.status == 200:
                    async with aiofiles.open(dest, "wb") as f:
                        await f.write(await r.read())
        except Exception as e:
            print(f"skip {slug}: {e}")

async def main():
    slugs = Path("slugs.txt").read_text().splitlines()
    async with aiohttp.ClientSession() as s:
        await asyncio.gather(*(grab(s, x) for x in slugs))

asyncio.run(main())
