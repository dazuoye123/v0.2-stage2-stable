"""This module is kept for backward compatibility.
New code should import from alumina_sol_extractor.stage5.dataset_fusion.loaders.
"""

from importlib import import_module as _import_module
import sys as _sys

_impl = _import_module('alumina_sol_extractor.stage5.dataset_fusion.loaders')
_sys.modules[__name__] = _impl
