from __future__ import annotations

import math
import re
from typing import Any

from .io import normalize_text, safe_float


CATEGORY_ALIASES = {
    "applications": "applications",
    "application": "applications",
    "fiber_process": "fiber_process",
    "fiber process": "fiber_process",
    "mechanism": "mechanism",
    "rheology": "rheology",
}


def normalize_category(value: Any) -> str:
    text = normalize_text(value).lower().replace("-", "_")
    return CATEGORY_ALIASES.get(text, "uncategorized" if text else "uncategorized")


def normalize_parameter_family(*values: Any) -> str:
    text = " ".join(normalize_text(value).lower() for value in values if normalize_text(value))
    if not text:
        return "Unknown"
    if re.search(r"\bph\b|酸碱|peptiz|acid\/al|base\/al|hydrolysis ratio", text):
        return "pH" if "ph" in text else "acid/base ratio"
    if any(token in text for token in ("al concentration", "concentration", "浓度", "wt%", "mol/l")):
        return "Al concentration"
    if any(token in text for token in ("solid content", "solid_content", "固含")):
        return "solid content"
    if any(token in text for token in ("acid/al", "base_to_aluminum", "molar ratio", "ratio")):
        return "acid/base ratio"
    if any(token in text for token in ("hydrolysis_temperature", "hydrolysis temp")):
        return "hydrolysis temperature"
    if any(token in text for token in ("hydrolysis_time", "hydrolysis time")):
        return "hydrolysis time"
    if any(token in text for token in ("aging_temperature", "aging temp", "aging t")):
        return "aging temperature"
    if any(token in text for token in ("aging_time", "aging time")):
        return "aging time"
    if any(token in text for token in ("viscosity", "rheology", "流变")):
        return "viscosity/rheology"
    if any(token in text for token in ("spinneret", "spinning", "take_up", "electrospinning", "dry spinning")):
        return "spinning parameter"
    if any(token in text for token in ("drying_temperature", "drying temp")):
        return "drying temperature"
    if any(token in text for token in ("drying_time", "drying time")):
        return "drying time"
    if any(token in text for token in ("calcination_temperature", "calcination temp", "target_temperature", "煅烧")):
        return "calcination temperature"
    if any(token in text for token in ("holding_time", "holding time", "保温")):
        return "holding time"
    if any(token in text for token in ("heating_rate", "升温速率")):
        return "heating rate"
    if any(token in text for token in ("fiber_diameter", "diameter_estimate", "fiber diam")):
        return "fiber diameter"
    if any(token in text for token in ("particle_size", "dls", "粒径")):
        return "particle size"
    if any(token in text for token in ("bet", "surface area", "ssa")):
        return "BET surface area"
    if any(token in text for token in ("mass loss", "weight loss")):
        return "mass loss"
    if any(token in text for token in ("nmr", "ppm", "27al peak")):
        return "NMR shift"
    if any(token in text for token in ("ftir", "cm^-1", "cm-1", "infrared")):
        return "FTIR peak"
    if any(token in text for token in ("xrd", "2theta", "diffraction")):
        return "XRD peak"
    if any(token in text for token in ("tg", "dsc", "thermal", "endothermic", "exothermic")):
        return "TG/DSC event"
    if "zeta" in text:
        return "zeta potential"
    if any(token in text for token in ("tensile", "strength", "mechanical", "modulus")):
        return "mechanical property"
    if any(token in text for token in ("phase", "corundum", "boehmite", "gamma alumina", "alpha alumina")):
        return "phase composition"
    if any(token in text for token in ("crystallinity", "crystallite")):
        return "crystallinity"
    if any(token in text for token in ("density", "porosity", "pore")):
        return "density/porosity"
    return "other"


def normalize_spectra_type(*values: Any) -> str:
    text = " ".join(normalize_text(value).lower().replace("-", " ").replace("_", " ") for value in values if normalize_text(value))
    text = " ".join(text.split())
    padded = f" {text} "
    if not text or text == "unknown":
        return "Unknown"
    if any(token in text for token in ("nmr", "ppm")):
        return "NMR"
    if any(token in text for token in ("ftir", "infrared", "ft ir")):
        return "FTIR"
    if any(token in text for token in ("xrd", "x ray diffraction", "diffraction")):
        return "XRD"
    if "raman" in text:
        return "Raman"
    if any(token in text for token in ("tg dsc", "tga dsc", "dsc/tg", "thermal event", "thermogravimetric", "differential scanning calorimetry", "dsc", "tga")):
        return "TG/DSC"
    if any(token in text for token in ("sem", "tem", "fesem", "hrtem", "scanning electron microscopy", "transmission electron microscopy", "stem", "haadf", "saed")) or " sem " in padded or " tem " in padded:
        return "SEM/TEM microscopy"
    if any(token in text for token in ("optical microscopy", "microscopy", "photo", "photography", "afm")):
        return "Optical microscopy/photo"
    if any(token in text for token in ("rheology", "viscosity", "viscometry")):
        return "Rheology"
    if any(token in text for token in ("particle size", "dls", "dynamic light scattering")):
        return "Particle size"
    if "zeta" in text:
        return "Zeta potential"
    if any(token in text for token in ("bet", "surface area", "nitrogen adsorption", "n2 adsorption")):
        return "BET"
    if any(token in text for token in ("mechanical", "tensile", "compression")):
        return "Mechanical"
    if "ferron" in text:
        return "Ferron"
    if "simulation" in text or "molecular dynamics" in text or "dft" in text:
        return "Simulation"
    return "Other"


def normalize_process_step_family(*values: Any) -> str:
    text = " ".join(normalize_text(value).lower() for value in values if normalize_text(value))
    if not text:
        return "Unknown"
    if any(token in text for token in ("precursor", "dissolve", "mix", "solution")):
        return "precursor preparation"
    if "hydrolysis" in text:
        return "hydrolysis"
    if any(token in text for token in ("peptization", "peptize")):
        return "peptization"
    if "aging" in text:
        return "aging"
    if any(token in text for token in ("concentration", "evapor", "condense")):
        return "concentration"
    if any(token in text for token in ("spin", "electrospin", "spinneret")):
        return "spinning"
    if "dry" in text:
        return "drying"
    if any(token in text for token in ("calcination", "heat", "furnace", "煅烧")):
        return "calcination"
    if "sinter" in text:
        return "sintering"
    if any(token in text for token in ("wash", "filtration", "filter", "centrifuge")):
        return "washing/filtration"
    if any(token in text for token in ("characterization", "ftir", "xrd", "sem", "tem", "test")):
        return "characterization"
    if any(token in text for token in ("application", "permeation", "catalytic", "adsorption", "mechanical")):
        return "application testing"
    return "other"


def normalize_numeric_value(value: Any, unit: Any, family: str) -> tuple[float | None, str | None, str | None]:
    numeric = safe_float(value)
    unit_text = normalize_text(unit)
    if numeric is None:
        return None, None, None
    family_lower = family.lower()
    if family in {"pH"}:
        return numeric, "unitless", None
    if "temperature" in family_lower or family in {"TG/DSC event"}:
        return _to_celsius(numeric, unit_text), "°C", None
    if "time" in family_lower or family in {"holding time"}:
        return _to_hours(numeric, unit_text), "h", None
    if family in {"fiber diameter"}:
        normalized, note = _to_preferred_size(numeric, unit_text, preferred="μm")
        return normalized, "μm", note
    if family in {"particle size"}:
        normalized, note = _to_preferred_size(numeric, unit_text, preferred="nm")
        return normalized, "nm", note
    if family in {"BET surface area"}:
        return numeric, "m²/g", None
    if family in {"FTIR peak"}:
        return numeric, "cm^-1", None
    if family in {"XRD peak"}:
        return numeric, "2θ degree", None
    if family in {"NMR shift"}:
        return numeric, "ppm", None
    if family in {"zeta potential"}:
        return numeric, "mV", None
    return numeric, unit_text or None, None


def _to_celsius(value: float, unit: str) -> float:
    unit = unit.lower()
    if "k" == unit or "kelvin" in unit:
        return value - 273.15
    return value


def _to_hours(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit in {"min", "mins", "minute", "minutes"}:
        return value / 60.0
    if unit in {"s", "sec", "second", "seconds"}:
        return value / 3600.0
    return value


def _to_preferred_size(value: float, unit: str, *, preferred: str) -> tuple[float, str | None]:
    normalized_unit = unit.lower()
    if preferred == "nm":
        if normalized_unit in {"μm", "um", "mum"}:
            return value * 1000.0, "converted_from_um"
        return value, None
    if preferred == "μm":
        if normalized_unit == "nm":
            return value / 1000.0, "converted_from_nm"
        return value, None
    return value, None
