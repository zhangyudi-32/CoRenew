
from __future__ import annotations

from importlib import import_module

_MODULE_NAMES = [
    "core",
    "visualization",
    "controllers",
    "html_shell",
    "pages",
    "gradio_ui",
    "fastapi_app",
    "static_export",
]

_modules = [import_module(f"{__name__}.{module_name}") for module_name in _MODULE_NAMES]
_exports = {}
for _module in _modules:
    for _name, _value in vars(_module).items():
        if _name in {"_core"} or (_name.startswith("__") and _name.endswith("__")):
            continue
        _exports[_name] = _value

for _module in _modules:
    _module.__dict__.update(_exports)

globals().update(_exports)
__all__ = sorted(_exports)
