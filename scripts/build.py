"""Build helper for Chiron — calls PyInstaller and sets up the dist folder.

Usage:
    python scripts/build.py            # Standard build
    python scripts/build.py --clean    # Remove build/ + dist/ first
    python scripts/build.py --dry-run  # Show what would be done
"""

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "chiron.spec"
DIST = ROOT / "dist" / "chiron"
BUILD = ROOT / "build"

# Read version from pyproject.toml (single source of truth)
with open(ROOT / "pyproject.toml", "rb") as f:
    _meta = tomllib.load(f)
_VERSION = _meta["project"]["version"]
_EXE_NAME = f"chiron-{_VERSION}.exe"

# Directories to create inside dist/chiron/data/
DATA_SUBDIRS = [
    "db",
]


def clean(dry_run: bool = False) -> None:
    """Remove build/ and dist/ directories."""
    for d in (BUILD, ROOT / "dist"):
        if d.exists():
            print(f"{'[DRY-RUN] ' if dry_run else ''}Removing {d}")
            if not dry_run:
                shutil.rmtree(d)


def run_pyinstaller(dry_run: bool = False) -> None:
    """Run PyInstaller with the spec file."""
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"]
    print(f"{'[DRY-RUN] ' if dry_run else ''}Running: {' '.join(cmd)}")
    if not dry_run:
        subprocess.check_call(cmd, cwd=str(ROOT))


# Simplified .env.example written into dist/ (the full version stays in repo)
_DIST_ENV_EXAMPLE = """\
# =============================================================================
# Chiron - Configuration
# =============================================================================
# Renommer ce fichier en .env et remplir votre cle API Mistral.

# Cle API Mistral (https://console.mistral.ai/)
# Mistral est heberge en UE, conforme RGPD.
MISTRAL_API_KEY=
"""


def post_build(dry_run: bool = False) -> None:
    """Create data directories and write simplified .env.example."""
    # Create data subdirectories
    for subdir in DATA_SUBDIRS:
        target = DIST / "data" / subdir
        print(f"{'[DRY-RUN] ' if dry_run else ''}Creating {target}")
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)

    # Write simplified .env.example next to exe
    dist_env = DIST / ".env.example"
    print(f"{'[DRY-RUN] ' if dry_run else ''}Writing {dist_env}")
    if not dry_run:
        dist_env.write_text(_DIST_ENV_EXAMPLE, encoding="utf-8")

    # Remove the full .env.example that PyInstaller may have copied into _internal
    internal_env = DIST / "_internal" / ".env.example"
    if not dry_run and internal_env.exists():
        internal_env.unlink()

    # Copy demo PDF into data/demo/ if it exists in the source tree
    demo_pdf_src = ROOT / "data" / "demo" / "Bulletin_TEST.pdf"
    demo_dir = DIST / "data" / "demo"
    demo_pdf_dst = demo_dir / "Bulletin_TEST.pdf"
    if demo_pdf_src.exists():
        print(f"{'[DRY-RUN] ' if dry_run else ''}Creating {demo_dir}")
        print(f"{'[DRY-RUN] ' if dry_run else ''}Copying demo PDF {demo_pdf_dst}")
        if not dry_run:
            demo_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(demo_pdf_src, demo_pdf_dst)


def print_instructions() -> None:
    """Print post-build instructions."""
    print()
    print("=" * 60)
    print("BUILD COMPLETE")
    print("=" * 60)
    print(f"  Output: {DIST}")
    print()
    print("  Next steps:")
    print(f"  1. Copy your .env to {DIST / '.env'}")
    print(f"     (see {DIST / '.env.example'} for template)")
    print(f"  2. Run {DIST / _EXE_NAME}")
    print("     The browser will open automatically.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Chiron with PyInstaller")
    parser.add_argument(
        "--clean", action="store_true", help="Remove build/ and dist/ before building"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing",
    )
    args = parser.parse_args()

    if args.clean:
        clean(dry_run=args.dry_run)

    run_pyinstaller(dry_run=args.dry_run)
    post_build(dry_run=args.dry_run)
    print_instructions()


if __name__ == "__main__":
    main()
