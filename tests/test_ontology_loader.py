from __future__ import annotations

from pathlib import Path

from alumina_sol_extractor.ontology import get_canonical_keys, load_ontology_config, normalize_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ontology_loader_reads_configs_file() -> None:
    config = load_ontology_config(PROJECT_ROOT)
    assert "parameters" in config
    assert isinstance(config["parameters"], list)


def test_ontology_loader_returns_canonical_keys() -> None:
    keys = get_canonical_keys(PROJECT_ROOT)
    assert "viscosity_Pa_s" in keys
    assert "solid_content_wt_percent" in keys


def test_normalize_key_matches_aliases() -> None:
    assert normalize_key("viscosity", PROJECT_ROOT) == "viscosity_Pa_s"
