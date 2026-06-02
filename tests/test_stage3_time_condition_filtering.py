from __future__ import annotations

import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "dev" / "build_stage3_analysis_v2.py"
AUDIT_SCRIPT = PROJECT_ROOT / "scripts" / "dev" / "generate_classification_audit.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_stage3_analysis_v2", BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("generate_classification_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================================
# Test 1: 10000 Hz must NOT be parsed as time
# "spectral width 10000 Hz" → non_time_unit_context
# ============================================================================
def test_spectral_width_hz_excluded_by_is_likely_time_value() -> None:
    """10000 Hz should be excluded as non_time_unit_context."""
    mod = _load_build_module()
    evidence = (
        "Record spectra at 25degC with Bruker WP 200 spectrometer at "
        "52.148 MHz. Pulse width 47.6 us, acquisition time 0.819 s, "
        "spectral width 10000 Hz."
    )
    # Case: condition_value=10000.0, condition_unit="h", evidence contains Hz
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="10000.0",
        condition_unit="h",
        evidence_text=evidence,
        condition_key="duration",
    )
    assert not is_time, f"10000 Hz should NOT be time: reason={reason}"
    assert reason == "non_time_unit_context"


def test_spectral_width_hz_excluded_by_audit_is_likely_time_value() -> None:
    """Same check in audit script."""
    mod = _load_audit_module()
    evidence = (
        "Record spectra at 25degC with Bruker WP 200 spectrometer at "
        "52.148 MHz. Pulse width 47.6 us, acquisition time 0.819 s, "
        "spectral width 10000 Hz."
    )
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="10000.0",
        condition_unit="h",
        evidence_text=evidence,
        condition_key="duration",
    )
    assert not is_time


def test_acquisition_time_0_819s_is_valid_time() -> None:
    """0.819 s acquisition time CAN be recognized as measurement_time."""
    mod = _load_build_module()
    evidence = (
        "Pulse width 47.6 us, acquisition time 0.819 s, spectral width 10000 Hz."
    )
    # When condition_value="0.819" and unit="s", it should pass the check
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="0.819",
        condition_unit="s",
        evidence_text=evidence,
        condition_key="duration",
    )
    assert is_time, f"0.819 s should be recognized as time: reason={reason}"


# ============================================================================
# Test 2: 500degC must NOT be parsed as calcination_holding_time
# ============================================================================
def test_500c_temperature_excluded() -> None:
    """500degC保温除有机物 should not become 500h time."""
    mod = _load_build_module()
    evidence = "将凝胶纤维进行程序升温煅烧(如室温至1200degC)，去除有机物和结构水，转化为氧化铝陶瓷纤维。"

    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="500degC保温除有机物",
        condition_unit="",
        evidence_text=evidence,
        condition_key="保温",
    )
    assert not is_time, f"500degC should NOT be time: reason={reason}"


def test_500c_temperature_excluded_audit() -> None:
    """Same check in audit script."""
    mod = _load_audit_module()
    evidence = "将凝胶纤维进行程序升温煅烧(如室温至1200degC)，去除有机物和结构水，转化为氧化铝陶瓷纤维。"

    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="500degC保温除有机物",
        condition_unit="",
        evidence_text=evidence,
        condition_key="保温",
    )
    assert not is_time


# ============================================================================
# Test 3: 800degC煅烧2h — 2h is calcination_holding_time, 800degC is NOT time
# ============================================================================
def test_calcination_2h_is_valid_time() -> None:
    """2h calcination should pass is_likely_time_value."""
    mod = _load_build_module()
    evidence = "将前驱体纤维在800degC煅烧2h，进行晶相转化"

    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="2",
        condition_unit="h",
        evidence_text=evidence,
        condition_key="holding_time",
    )
    assert is_time, f"2h calcination should be time: reason={reason}"


def test_800c_not_mistaken_for_time() -> None:
    """800degC should NOT be parsed as time."""
    mod = _load_build_module()
    evidence = "将前驱体纤维在800degC煅烧2h，进行晶相转化"

    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="800",
        condition_unit="",
        evidence_text=evidence,
        condition_key="temperature",
    )
    # With condition_key=temperature, not time-related, the
    # is_likely_time_value check catches the degC context
    assert not is_time


# ============================================================================
# Test 4: Sintering at 1200degC for 0.5h — 0.5h valid, 1200degC not
# ============================================================================
def test_sintering_0_5h_is_valid_time() -> None:
    """0.5 h sintering should pass."""
    mod = _load_build_module()
    evidence = "Sinter pyrolyzed fibers at 1200 degC for 0.5 h"

    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="0.5",
        condition_unit="h",
        evidence_text=evidence,
        condition_key="holding_time",
    )
    assert is_time, f"0.5h sintering should be time: reason={reason}"


def test_1200c_not_mistaken_for_time() -> None:
    """1200degC should NOT be parsed as time."""
    mod = _load_build_module()
    evidence = "Sinter pyrolyzed fibers at 1200 degC for 0.5 h"

    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="1200",
        condition_unit="degC",
        evidence_text=evidence,
        condition_key="temperature",
    )
    assert not is_time


# ============================================================================
# Test 5: "averaging correlograms for 1-5 min" must NOT match aging_time
# ============================================================================
def test_averaging_correlograms_not_aging_time() -> None:
    """averaging should NOT trigger aging word-boundary match."""
    mod = _load_build_module()
    # Test the regex directly
    assert hasattr(mod, "_AGING_EN_PATTERN")
    pattern = mod._AGING_EN_PATTERN
    # "averaging" should NOT match
    assert not pattern.search("averaging correlograms for 1-5 min")
    # "aging" should match
    assert pattern.search("aging for 2 hours")
    # "aged" should match
    assert pattern.search("aged for 24 h")
    # "ageing" should match
    assert pattern.search("ageing for 12 h")
    # "average" should NOT match
    assert not pattern.search("average particle size")


def test_dls_measurement_classified_as_measurement_not_aging() -> None:
    """DLS correlogram averaging should be measurement_time, not aging_time."""
    mod = _load_build_module()
    time_type = mod.infer_time_condition_type(
        condition_key="duration",
        action="other",
        evidence_text="Perform DLS measurements by averaging correlograms for 1-5 min",
    )
    assert time_type == "measurement_time", f"Expected measurement_time, got {time_type}"


def test_averaging_correlograms_not_aging_audit() -> None:
    """Same check in audit script."""
    mod = _load_audit_module()
    time_type, _, _, _ = mod.infer_time_condition_type_with_audit(
        condition_key="duration",
        action="other",
        evidence_text="Perform DLS measurements by averaging correlograms for 1-5 min",
    )
    assert time_type == "measurement_time"


# ============================================================================
# Test 6: Generic non-time unit checks
# ============================================================================
def test_rpm_not_time() -> None:
    """3000 rpm should not be time."""
    mod = _load_build_module()
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="3000",
        condition_unit="rpm",
        evidence_text="Separate gel fibers",
        condition_key="duration",
    )
    assert not is_time


def test_mpa_not_time() -> None:
    """Pressure unit should not be time."""
    mod = _load_build_module()
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="0.6",
        condition_unit="MPa",
        evidence_text="gas pressure 0.6 MPa",
        condition_key="duration",
    )
    assert not is_time


def test_nm_not_time() -> None:
    """Nanometer should not be time."""
    mod = _load_build_module()
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="100",
        condition_unit="nm",
        evidence_text="particle size 100 nm",
        condition_key="time",
    )
    assert not is_time


def test_valid_time_unit_h_still_passes() -> None:
    """Valid h unit with proper context should pass."""
    mod = _load_build_module()
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="2",
        condition_unit="h",
        evidence_text="stir for 2 h at room temperature",
        condition_key="stirring_time",
    )
    assert is_time
    assert reason == ""


def test_valid_time_unit_min_still_passes() -> None:
    """Valid min unit with proper context should pass."""
    mod = _load_build_module()
    is_time, reason = mod.is_likely_time_value(
        raw_condition_value="30",
        condition_unit="min",
        evidence_text="dry at 120degC for 30 min",
        condition_key="drying_time",
    )
    assert is_time
    assert reason == ""
