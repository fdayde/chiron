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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "chiron.spec"
DIST = ROOT / "dist" / "chiron"
BUILD = ROOT / "build"

# Directories to create inside dist/chiron/data/
DATA_SUBDIRS = [
    "db",
    "raw",
    "processed",
    "processed/logs",
    "exports",
    "mapping",
    "ground_truth",
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
# Renommer ce fichier en .env et remplir la cle du provider choisi.

# Provider par defaut : openai, anthropic ou mistral
DEFAULT_PROVIDER=anthropic

# Cles API (remplir uniquement celle du provider choisi)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
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
    print(f"  2. Run {DIST / 'chiron.exe'}")
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
