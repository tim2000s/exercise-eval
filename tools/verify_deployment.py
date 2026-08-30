"""Check that the published site is byte-for-byte the files the tests ran against.

The browser checks run against a local copy, because Chrome's Private Network Access rules stop
a page served from a public origin from reporting back to a harness on localhost. Comparing what
Pages serves against the working tree closes the same gap more directly: if the bytes match and
the local checks pass, the deployed site behaves the same way.

Every file the site actually loads is checked, including the Python package, because the page
fetches those at runtime and a single missing module breaks the analysis with a 404 that is not
visible from the interface.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://tim2000s.github.io/exercise-eval"
ROOT = Path(__file__).resolve().parent.parent

#: Directories the page loads at runtime. Everything under them that git tracks is compared.
PUBLISHED = ("css", "js", "python", "vendor", "docs")
TOP_LEVEL = ("index.html", "README.md", "LICENCE", ".nojekyll")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.split()
    keep = [f for f in out if f.startswith(PUBLISHED) or f in TOP_LEVEL]
    # Nothing under tests/ or tools/ is loaded by the page, and the fixtures are generated.
    return sorted(f for f in keep if not f.endswith(".pyc"))


def check(rel: str) -> tuple[str, str, str]:
    local = (ROOT / rel).read_bytes()
    try:
        with urllib.request.urlopen(f"{BASE}/{rel}", timeout=30) as r:
            remote = r.read()
    except urllib.error.HTTPError as e:
        return rel, "missing", f"HTTP {e.code}"
    except Exception as e:  # network trouble is not the same as a mismatch
        return rel, "error", str(e)
    if remote == local:
        return rel, "ok", f"{len(local):,d} B"
    return rel, "differs", (
        f"local {hashlib.sha256(local).hexdigest()[:12]} "
        f"({len(local):,d} B) vs served "
        f"{hashlib.sha256(remote).hexdigest()[:12]} ({len(remote):,d} B)"
    )


def main() -> int:
    files = tracked_files()
    print(f"Comparing {len(files)} published files against {BASE}\n")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, files))

    bad = [r for r in results if r[1] != "ok"]
    for rel, status, detail in results:
        if status != "ok":
            print(f"  {status.upper():8s} {rel}\n           {detail}")

    print(f"\n{len(results) - len(bad)} of {len(results)} files match the working tree.")
    if bad:
        print("The deployed site is not the code these tests ran against.")
        return 1
    print("The deployed site is byte-for-byte the code the browser checks passed on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
