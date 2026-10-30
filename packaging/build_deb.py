#!/usr/bin/env python3
"""Assemble and build an architecture-independent Debian binary package."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "chali"
VERSION = "0.1.0"


def main() -> int:
    if not shutil.which("dpkg-deb"):
        print("dpkg-deb is required; run this build on Debian or Ubuntu.", file=sys.stderr)
        return 2
    source = ROOT / PACKAGE
    native_extensions = list(source.rglob("*.so")) + list(source.rglob("*.pyd")) + list(source.rglob("*.dll"))
    if native_extensions:
        print("Refusing Architecture: all package: native extensions were found.", file=sys.stderr)
        return 2
    output_dir = ROOT / "dist"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"{PACKAGE}_{VERSION}_all.deb"
    with tempfile.TemporaryDirectory(prefix="chali-deb-") as temporary:
        stage = Path(temporary)
        shutil.copytree(ROOT / "packaging" / "DEBIAN", stage / "DEBIAN")
        shutil.copytree(
            source,
            stage / "usr" / "lib" / "chali" / PACKAGE,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        launcher = stage / "usr" / "bin" / PACKAGE
        launcher.parent.mkdir(parents=True, exist_ok=True)
        launcher.write_text(
            "#!/usr/bin/python3\n"
            "import sys\n"
            "sys.path.insert(0, '/usr/lib/chali')\n"
            "from chali.cli import main\n"
            "raise SystemExit(main())\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output)], check=True)
    print(f"Built {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
