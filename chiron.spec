# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Chiron — --onedir, console, web mode."""

import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

block_cipher = None

# ---------------------------------------------------------------------------
# Paths & version
# ---------------------------------------------------------------------------
ROOT = Path(SPECPATH)

import tomllib

with open(ROOT / "pyproject.toml", "rb") as f:
    _meta = tomllib.load(f)
_VERSION = _meta["project"]["version"]

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hidden_imports = [
    # NiceGUI pages (imported dynamically in run.py)
    "pages.home",
    "pages.import_page",
    "pages.syntheses",
    "pages.export",
    "pages.prompt",
    # App modules
    "cache",
    "layout",
    "state",
    "config_ng",
    "components",
    "components.appreciations_view_ng",
    "components.eleve_card_ng",
    "components.llm_selector_ng",
    "components.metric_card_ng",
    "components.synthese_editor_ng",
    "components.data_helpers",
    "components.sidebar",
    # uvicorn internals
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    # FastAPI / multipart
    "multipart",
    "python_multipart",
    # Flair NER
    "flair",
    "flair.models",
    "flair.data",
    "flair.nn",
    # pydantic / pydantic-settings
    "pydantic",
    "pydantic_settings",
    # protobuf (needed by transformers / onnx at runtime)
    "google.protobuf",
]

# Collect all src.* submodules
hidden_imports += collect_submodules("src")

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = []

# App directory (pages, components, etc.) → _internal/app/
datas += [(str(ROOT / "app"), "app")]

# .env.example → next to exe (will be moved post-build by scripts/build.py)
datas += [(str(ROOT / ".env.example"), ".")]

# NiceGUI assets
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all("nicegui")
datas += nicegui_datas
hidden_imports += nicegui_hiddenimports

# Transformers data files (tokenizer configs, etc.)
datas += collect_data_files("transformers")

# Flair data files
datas += collect_data_files("flair")

# Package metadata needed at runtime
for pkg in [
    "chiron",
    "nicegui",
    "fastapi",
    "uvicorn",
    "starlette",
    "pydantic",
    "pydantic_settings",
    "pydantic_core",
    "httpx",
    "httpcore",
    "h11",
    "anyio",
    "sniffio",
    "idna",
    "certifi",
    "transformers",
    "huggingface_hub",
    "tokenizers",
    "safetensors",
    "tqdm",
    "torch",
    "numpy",
    "pandas",
    "duckdb",
    "openpyxl",
    "pdfplumber",
    "reportlab",
    "tenacity",
    "python_dotenv",
    "cachetools",
    "nest_asyncio",
    "python_multipart",
    "langdetect",
    "protobuf",
    "flair",
    "rapidfuzz",
]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass  # Package not installed or no metadata

# ---------------------------------------------------------------------------
# Exclusions — packages in pyproject.toml but unused by the NiceGUI app
# ---------------------------------------------------------------------------
excludes = [
    "spacy",
    "fr_core_news_lg",
    "sentence_transformers",
    "docling",
    "marker",
    "streamlit",
    "matplotlib",
    "seaborn",
    "pytest",
    "ruff",
    "pre_commit",
    "tkinter",
    "_tkinter",
    # Transitive deps not used by the app
    "cv2",
    "opencv_python",
    "scipy",
    "pyarrow",
    "torchvision",
    "torchtext",
    "torchaudio",
    # pythonnet — not needed: pywebview uses edgechromium backend on Windows
    "pythonnet",
    "clr",
    "clr_loader",
]

# ---------------------------------------------------------------------------
# CUDA binary stripping — keep only CPU torch
# ---------------------------------------------------------------------------
CUDA_PATTERNS = [
    "cublas",
    "cudnn",
    "cusparse",
    "cufft",
    "curand",
    "nccl",
    "nvrtc",
    "cudart",
    "cusolver",
    "nvjitlink",
]


def strip_cuda(binaries):
    """Remove CUDA shared libs from the binary list."""
    filtered = []
    for dest, src, typecode in binaries:
        name_lower = dest.lower()
        if any(pattern in name_lower for pattern in CUDA_PATTERNS):
            continue
        filtered.append((dest, src, typecode))
    return filtered


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT), str(ROOT / "app")],
    binaries=nicegui_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    cipher=block_cipher,
)

# Strip CUDA binaries
a.binaries = strip_cuda(a.binaries)

# ---------------------------------------------------------------------------
# Splash screen — shown while Python loads
# ---------------------------------------------------------------------------
splash = Splash(
    str(ROOT / "app" / "static" / "chiron_logo.png"),
    binaries=a.binaries,
    datas=a.datas,
)

# ---------------------------------------------------------------------------
# PYZ / EXE / COLLECT
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    [],
    exclude_binaries=True,
    name=f"chiron-{_VERSION}",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="chiron",
)
