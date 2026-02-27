"""PyInstaller runtime hook — patch transformers lazy imports for frozen bundles.

Runs at Python startup, BEFORE the main script or any application import.

Fixes: in PyInstaller bundles, ``transformers``' ``_LazyModule.__getattr__``
can fail to resolve certain classes (e.g. ``AutoFeatureExtractor``) because
the import chain pulls in excluded packages (scipy via sklearn).

We force-import the specific submodules flair needs via absolute imports
(handled by PyInstaller's FrozenImporter) and inject their public names
into the top-level ``transformers`` namespace.
"""

import importlib


def _patch():
    _submodules = [
        "transformers.models.auto.configuration_auto",
        "transformers.models.auto.feature_extraction_auto",
        "transformers.models.auto.tokenization_auto",
    ]

    try:
        transformers = importlib.import_module("transformers")
    except Exception:
        return

    for fqn in _submodules:
        try:
            mod = importlib.import_module(fqn)
            for name in getattr(mod, "__all__", []):
                obj = getattr(mod, name, None)
                if obj is not None:
                    setattr(transformers, name, obj)
        except Exception:
            pass


_patch()
del _patch
