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
                        "image_caption": [{"type": "text", "content": "\u56fe1 \u6d4b\u8bd5\u56fe"}],
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
        assert layout["images/a.jpg"]["caption"] == "\u56fe1 \u6d4b\u8bd5\u56fe"
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
                                "image_caption": [{"type": "text", "content": "\u56fe2 \u7b2c\u4e8c\u9875\u56fe"}],
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
        assert layout["images/b.jpg"]["caption"] == "\u56fe2 \u7b2c\u4e8c\u9875\u56fe"
        assert layout["b.jpg"]["source"] == "content_list_v2"


def test_model_json_normalized_bbox_with_page_size() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "model.json").write_text(
            json.dumps(
                [
                    {
                        "type": "image",
                        "path": "images/c.jpg",
                        "page_idx": 0,
                        "page_width": 1000,
                        "page_height": 2000,
                        "bbox": [0.1, 0.2, 0.3, 0.4],
                    }
                ]
            ),
            encoding="utf-8",
        )

        layout = load_mineru_image_layout(root)

        assert layout["images/c.jpg"]["bbox"] == [100.0, 400.0, 300.0, 800.0]
        assert layout["images/c.jpg"]["bbox_format"] == "pixel"
        assert layout["images/c.jpg"]["source"] == "model_json"


if __name__ == "__main__":
    test_content_list_json()
    test_content_list_v2_json()
    test_model_json_normalized_bbox_with_page_size()
    print("mineru layout parser test passed")
