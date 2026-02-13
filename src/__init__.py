from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("chiron")
except PackageNotFoundError:
    import tomllib
    from pathlib import Path

    _pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if _pyproject.exists():
        with open(_pyproject, "rb") as _f:
            __version__ = tomllib.load(_f)["project"]["version"]
    else:
        __version__ = "dev"
