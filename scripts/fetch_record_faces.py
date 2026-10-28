"""Fetch synthetic mugshot faces for the demo criminal-records database.

FLUXSynID (Zenodo 15172770, CC BY-NC 4.0) is ~15k synthetic identities in one 11.7 GB zip.
Range requests read only the files needed: each identity's attributes, its ID-style front
photo and one live photo, for adults of the chosen origin. Nobody in these photos exists.

  uv run --with remotezip python -m scripts.fetch_record_faces [count=120] [origin]

Writes storage/records/faces/<id>_doc.jpg, <id>_live.jpg and storage/records/faces.json.
"""

import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from remotezip import RemoteIOError, RemoteZip

URL = "https://zenodo.org/api/records/15172770/files/FLUXSynID.zip/content"
OUT = Path("storage/records/faces")

_local = threading.local()


def _zip() -> RemoteZip:
    if not hasattr(_local, "z"):
        _local.z = RemoteZip(URL)
    return _local.z


def _read(name: str) -> bytes:
    """Zenodo rate-limits (429): back off and retry rather than give up."""
    for attempt in range(8):
        try:
            return _zip().read(name)
        except RemoteIOError as e:
            if "429" not in str(e) and attempt > 1:
                raise
            time.sleep(min(60, 5 * 2**attempt) + random.random() * 3)
    raise RuntimeError(f"gave up on {name}")


def main(count: int = 120, origin: str = "South Asian") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    index = OUT.parent / "faces.json"
    # resume: identities already saved, and metadata already looked at
    found: list[dict] = json.loads(index.read_text()) if index.exists() else []
    seen_path = OUT.parent / "seen.txt"
    seen = set(seen_path.read_text().split()) if seen_path.exists() else set()
    names = RemoteZip(URL).namelist()
    metas = [n for n in names if (n.endswith("_f.json") or n.endswith("_m.json")) and n not in seen]
    files = set(names)
    lock = threading.Lock()

    def save() -> None:
        index.write_text(json.dumps(sorted(found, key=lambda f: f["id"]), indent=1))
        seen_path.write_text("\n".join(sorted(seen)))

    def check(meta: str) -> None:
        if len(found) >= count:
            return
        info = json.loads(_read(meta))["attributes"]
        with lock:
            seen.add(meta)
        age = info.get("ages.txt") or ""
        if info.get("origins.txt") != origin or not age[:2].isdigit() or int(age[:2]) < 18:
            return
        stem = meta[: -len(".json")]
        live = sorted(n for n in files if n.startswith(stem + "_live_") and "_a_" in n) or sorted(
            n for n in files if n.startswith(stem + "_live_")
        )
        ident = Path(stem).name
        with lock:
            if len(found) >= count:
                return
        (OUT / f"{ident}_doc.jpg").write_bytes(_read(stem + "_doc.jpg"))
        if live:
            (OUT / f"{ident}_live.jpg").write_bytes(_read(live[0]))
        with lock:
            found.append({"id": ident, "gender": info.get("genders.txt"), "age": info.get("ages.txt"),
                          "hair": info.get("hair_colors.txt"), "attributes": info})
            save()
        print(f"{len(found)}/{count} {ident}", flush=True)

    with ThreadPoolExecutor(3) as pool:
        list(pool.map(check, metas))
    save()
    print(f"saved {len(found)} identities to {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120, sys.argv[2] if len(sys.argv) > 2 else "South Asian")
