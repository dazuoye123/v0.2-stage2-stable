"""This module is kept for backward compatibility.
New code should import from alumina_sol_extractor.stage2.taxonomy_classifier.
"""

from importlib import import_module as _import_module
import sys as _sys

_impl = _import_module('alumina_sol_extractor.stage2.taxonomy_classifier')
_sys.modules[__name__] = _impl
