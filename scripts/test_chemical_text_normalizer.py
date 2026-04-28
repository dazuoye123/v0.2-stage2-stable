"""Small smoke test for chemistry normalization."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.utils.chemical_text_normalizer import (  # noqa: E402
    normalize_mineru_markdown_chemistry,
)


def test_alpha_alumina_example() -> None:
    source = (
        r"关键词 $\alpha { \mathrm { \ - A l } } _ { 2 } "
        r"\mathrm { 0 } _ { 3 }$ ; 柔性纤维; 纳米结构; 静电纺丝"
    )
    expected = "关键词 α-Al2O3; 柔性纤维; 纳米结构; 静电纺丝"
    actual = normalize_mineru_markdown_chemistry(source)
    assert actual == expected, actual


if __name__ == "__main__":
    test_alpha_alumina_example()
    print("chemical_text_normalizer test passed")
