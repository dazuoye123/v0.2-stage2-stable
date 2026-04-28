"""Tests for MinerU layout JSON parsing."""

from pathlib import Path
import json
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alumina_sol_extractor.pdf.mineru_layout_parser import load_mineru_image_layout


def test_content_list_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "content_list.json").write_text(
            json.dumps(
                [
                    {
                        "type": "image",
                        "img_path": "images/a.jpg",
                        "page_idx": 3,
                        "bbox": [10, 20, 110, 220],
                        "image_caption": [{"type": "text", "content": "图1 测试图"}],
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        layout = load_mineru_image_layout(root)

        assert layout["images/a.jpg"]["page_idx"] == 3
        assert layout["images/a.jpg"]["bbox"] == [10.0, 20.0, 110.0, 220.0]
        assert layout["images/a.jpg"]["bbox_format"] == "pixel"
        assert layout["images/a.jpg"]["caption"] == "图1 测试图"
        assert layout["a.jpg"]["source"] == "content_list"


def test_content_list_v2_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "content_list_v2.json").write_text(
            json.dumps(
                [
                    [],
                    [
                        {
                            "type": "image",
                            "content": {
                                "image_source": {"path": "images/b.jpg"},
                                "image_caption": [{"type": "text", "content": "图2 第二页图"}],
                            },
                            "bbox": [1, 2, 3, 4],
                        }
                    ],
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        layout = load_mineru_image_layout(root)

        assert layout["images/b.jpg"]["page_idx"] == 1
        assert layout["images/b.jpg"]["page_number"] == 2
        assert layout["images/b.jpg"]["bbox"] == [1.0, 2.0, 3.0, 4.0]
        assert layout["images/b.jpg"]["caption"] == "图2 第二页图"
        assert layout["b.jpg"]["source"] == "content_list_v2"


if __name__ == "__main__":
    test_content_list_json()
    test_content_list_v2_json()
    print("mineru layout parser test passed")
