from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("chiron")
except PackageNotFoundError:
    __version__ = "dev"
