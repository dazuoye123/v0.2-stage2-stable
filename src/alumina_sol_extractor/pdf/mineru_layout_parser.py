"""Parse MinerU layout JSON files and expose image bbox metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_mineru_image_layout(mineru_output_dir: Path) -> dict[str, dict]:
    """Load MinerU image layout metadata from the best available JSON file.

    Priority:
    1. content_list_v2.json
    2. content_list.json
    3. model.json
    """
    mineru_output_dir = Path(mineru_output_dir)
    for filename, loader in [
        ("content_list_v2.json", _load_content_list_v2),
        ("content_list.json", _load_content_list),
        ("model.json", _load_model_json),
    ]:
        path = _find_first(mineru_output_dir, filename)
        if not path:
            continue
        mapping = loader(path)
        if mapping:
            return mapping
    return {}


def _load_content_list_v2(path: Path) -> dict[str, dict]:
    data = _read_json(path)
    mapping: dict[str, dict] = {}
    if not isinstance(data, list):
        return mapping
    for page_idx, page_blocks in enumerate(data):
        if not isinstance(page_blocks, list):
            continue
        for block in page_blocks:
            if not isinstance(block, dict) or block.get("type") != "image":
                continue
            content = block.get("content") if isinstance(block.get("content"), dict) else {}
            image_source = content.get("image_source") if isinstance(content.get("image_source"), dict) else {}
            image_path = image_source.get("path") or block.get("img_path") or block.get("image_path")
            bbox = block.get("bbox")
            if image_path and _valid_bbox(bbox):
                _add_layout(
                    mapping,
                    image_path=str(image_path),
                    page_idx=page_idx,
                    bbox=bbox,
                    bbox_format="pixel",
                    caption=_caption_from_content(content.get("image_caption")),
                    source="content_list_v2",
                )
    return mapping


def _load_content_list(path: Path) -> dict[str, dict]:
    data = _read_json(path)
    mapping: dict[str, dict] = {}
    blocks = data if isinstance(data, list) else data.get("content") if isinstance(data, dict) else []
    if not isinstance(blocks, list):
        return mapping
    for block in blocks:
        if not isinstance(block, dict):
            continue
        image_path = block.get("img_path") or block.get("image_path")
        if block.get("type") == "image":
            content = block.get("content") if isinstance(block.get("content"), dict) else {}
            image_source = content.get("image_source") if isinstance(content.get("image_source"), dict) else {}
            image_path = image_path or image_source.get("path")
        bbox = block.get("bbox")
        if image_path and _valid_bbox(bbox):
            _add_layout(
                mapping,
                image_path=str(image_path),
                page_idx=block.get("page_idx"),
                bbox=bbox,
                bbox_format="pixel",
                caption=_caption_from_content(block.get("image_caption") or block.get("caption")),
                source="content_list",
            )
    return mapping


def _load_model_json(path: Path) -> dict[str, dict]:
    data = _read_json(path)
    mapping: dict[str, dict] = {}
    for block in _walk_dicts(data):
        image_path = _first_existing_key(
            block,
            ["img_path", "image_path", "path", "file_name", "filename"],
        )
        if not image_path and isinstance(block.get("image_source"), dict):
            image_path = block["image_source"].get("path")
        bbox = _first_existing_key(block, ["bbox", "box", "position"])
        if image_path and _valid_bbox(bbox):
            bbox_format = "normalized" if _looks_normalized(bbox) else "pixel"
            if bbox_format == "normalized":
                page_size = _page_size_from_block(block)
                if page_size is None:
                    continue
                bbox = [
                    float(bbox[0]) * page_size[0],
                    float(bbox[1]) * page_size[1],
                    float(bbox[2]) * page_size[0],
                    float(bbox[3]) * page_size[1],
                ]
                bbox_format = "pixel"
            _add_layout(
                mapping,
                image_path=str(image_path),
                page_idx=block.get("page_idx") or block.get("page_id"),
                bbox=bbox,
                bbox_format=bbox_format,
                caption=_caption_from_content(block.get("caption") or block.get("image_caption")),
                source="model_json",
            )
    return mapping


def _add_layout(
    mapping: dict[str, dict],
    image_path: str,
    page_idx: int | None,
    bbox: list[float],
    bbox_format: str,
    caption: str | None,
    source: str,
) -> None:
    normalized = _normalize_path_key(image_path)
    record = {
        "page_idx": int(page_idx) if page_idx is not None else None,
        "page_number": int(page_idx) + 1 if page_idx is not None else None,
        "bbox": [float(value) for value in bbox],
        "bbox_format": bbox_format,
        "caption": caption,
        "source": source,
        "mineru_img_path": normalized,
    }
    mapping[normalized] = record
    mapping[Path(normalized).name] = record


def _find_first(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    direct = root / filename
    if direct.exists():
        return direct
    matches = sorted(root.rglob(filename))
    return matches[0] if matches else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _caption_from_content(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("content") or item.get("text") or ""))
        caption = " ".join(part.strip() for part in parts if part and part.strip())
        return caption or None
    if isinstance(value, dict):
        return str(value.get("content") or value.get("text") or "").strip() or None
    return None


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _first_existing_key(block: dict, keys: list[str]):
    for key in keys:
        if key in block and block[key] is not None:
            return block[key]
    return None


def _valid_bbox(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 4 and all(isinstance(item, (int, float)) for item in value)


def _looks_normalized(bbox: list[float]) -> bool:
    return all(0 <= float(value) <= 1 for value in bbox)


def _page_size_from_block(block: dict) -> tuple[float, float] | None:
    for width_key, height_key in [
        ("page_width", "page_height"),
        ("width", "height"),
        ("img_width", "img_height"),
    ]:
        width = block.get(width_key)
        height = block.get(height_key)
        if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 1 and height > 1:
            return float(width), float(height)
    page_size = block.get("page_size")
    if (
        isinstance(page_size, list)
        and len(page_size) >= 2
        and isinstance(page_size[0], (int, float))
        and isinstance(page_size[1], (int, float))
    ):
        return float(page_size[0]), float(page_size[1])
    return None


def _normalize_path_key(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")
