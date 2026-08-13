from __future__ import annotations

import io
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None


class ImageSegmentationDependencyError(RuntimeError):
    """Raised when an explicitly requested image component is unavailable."""


@dataclass(frozen=True)
class ImageRegion:
    page: int
    index: int
    bbox: tuple[float, float, float, float]
    image: bytes
    extension: str


@dataclass
class ImagePiece:
    index: int
    file: str
    pixel_bbox: list[int]
    width: int
    height: int


@dataclass
class ImageResult:
    page: int
    index: int
    pdf_bbox: list[float]
    source_width: int
    source_height: int
    status: str
    split_axis: str | None = None
    pieces: list[ImagePiece] = field(default_factory=list)
    reason: str | None = None


@dataclass
class ImageSegmentationSummary:
    status: str
    output_directory: str
    image_count: int = 0
    split_image_count: int = 0
    piece_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    results: list[ImageResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_exportable_image_block(
    block: dict[str, Any],
    *,
    page_width: float,
    page_height: float,
    include_page_scans: bool = False,
) -> bool:
    if block.get("type") != 1 or not isinstance(block.get("image"), (bytes, bytearray)):
        return False
    bbox = block.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return False
    x0, y0, x1, y1 = (float(value) for value in bbox)
    width = max(0.0, x1 - x0)
    height = max(0.0, y1 - y0)
    if width < 24 or height < 24:
        return False
    page_area = max(1.0, page_width * page_height)
    area_ratio = (width * height) / page_area
    return include_page_scans or area_ratio <= 0.8


def extract_image_regions(
    source: str | Path,
    *,
    start_page: int = 1,
    end_page: int | None = None,
    max_per_page: int = 50,
    include_page_scans: bool = False,
) -> list[ImageRegion]:
    if fitz is None:
        raise ImageSegmentationDependencyError("Image extraction requires PyMuPDF.")
    source_path = Path(source).expanduser().resolve()
    document = fitz.open(source_path)
    try:
        final_page = document.page_count if end_page is None else min(end_page, document.page_count)
        regions: list[ImageRegion] = []
        for page_number in range(start_page - 1, final_page):
            page = document.load_page(page_number)
            blocks = page.get_text("dict").get("blocks", [])
            image_blocks = [
                block
                for block in blocks
                if is_exportable_image_block(
                    block,
                    page_width=page.rect.width,
                    page_height=page.rect.height,
                    include_page_scans=include_page_scans,
                )
            ]
            image_blocks.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
            for index, block in enumerate(image_blocks[:max_per_page], start=1):
                regions.append(
                    ImageRegion(
                        page=page_number + 1,
                        index=index,
                        bbox=tuple(round(float(value), 3) for value in block["bbox"]),
                        image=bytes(block["image"]),
                        extension=str(block.get("ext") or "png"),
                    )
                )
        return regions
    finally:
        document.close()


def _require_pillow() -> Any:
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImageSegmentationDependencyError(
            "Image segmentation requires Pillow. Run install_windows.bat or install .[images]."
        ) from exc
    return Image


def _open_rgb(image_bytes: bytes) -> Any:
    Image = _require_pillow()
    source = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    background = Image.new("RGBA", source.size, "white")
    background.alpha_composite(source)
    return background.convert("RGB")


def _ink_mask(image: Any, tolerance: int) -> Any:
    Image = _require_pillow()
    from PIL import ImageChops, ImageStat

    width, height = image.size
    margin_x = max(1, min(width // 20, 10))
    margin_y = max(1, min(height // 20, 10))
    corners = Image.new("RGB", (margin_x * 2, margin_y * 2))
    corners.paste(image.crop((0, 0, margin_x, margin_y)), (0, 0))
    corners.paste(image.crop((width - margin_x, 0, width, margin_y)), (margin_x, 0))
    corners.paste(image.crop((0, height - margin_y, margin_x, height)), (0, margin_y))
    corners.paste(
        image.crop((width - margin_x, height - margin_y, width, height)),
        (margin_x, margin_y),
    )
    background = tuple(round(value) for value in ImageStat.Stat(corners).median)
    flat_background = Image.new("RGB", image.size, background)
    difference = ImageChops.difference(image, flat_background).convert("L")
    return difference.point(lambda value: 255 if value > tolerance else 0)


def _runs(values: list[bool]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(values + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            result.append((start, index))
            start = None
    return result


def _content_bounds(mask: Any, *, min_ink_ratio: float = 0.002) -> tuple[int, int, int, int] | None:
    width, height = mask.size
    pixels = mask.load()
    column_has_ink = [
        sum(1 for y in range(height) if pixels[x, y] > 0) / max(height, 1) > min_ink_ratio
        for x in range(width)
    ]
    row_has_ink = [
        sum(1 for x in range(width) if pixels[x, y] > 0) / max(width, 1) > min_ink_ratio
        for y in range(height)
    ]
    columns = [index for index, value in enumerate(column_has_ink) if value]
    rows = [index for index, value in enumerate(row_has_ink) if value]
    if not columns or not rows:
        return None
    return min(columns), min(rows), max(columns) + 1, max(rows) + 1


def _best_separator(
    mask: Any,
    box: tuple[int, int, int, int],
    *,
    min_gap_ratio: float,
    min_piece_pixels: int,
) -> tuple[str, int, int] | None:
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    pixels = mask.load()
    minimum_x_gap = max(3, round(width * min_gap_ratio))
    minimum_y_gap = max(3, round(height * min_gap_ratio))
    x_blank = [
        sum(1 for y in range(top, bottom) if pixels[x, y] > 0) / max(height, 1) < 0.003
        for x in range(left, right)
    ]
    y_blank = [
        sum(1 for x in range(left, right) if pixels[x, y] > 0) / max(width, 1) < 0.003
        for y in range(top, bottom)
    ]
    candidates: list[tuple[float, str, int, int]] = []
    for start, end in _runs(x_blank):
        absolute_start = left + start
        absolute_end = left + end
        if end - start < minimum_x_gap:
            continue
        if absolute_start - left < min_piece_pixels or right - absolute_end < min_piece_pixels:
            continue
        candidates.append(((end - start) / width, "vertical", absolute_start, absolute_end))
    for start, end in _runs(y_blank):
        absolute_start = top + start
        absolute_end = top + end
        if end - start < minimum_y_gap:
            continue
        if absolute_start - top < min_piece_pixels or bottom - absolute_end < min_piece_pixels:
            continue
        candidates.append(((end - start) / height, "horizontal", absolute_start, absolute_end))
    if not candidates:
        return None
    _, axis, start, end = max(candidates, key=lambda item: item[0])
    return axis, start, end


def split_image(
    image: Any,
    *,
    min_gap_ratio: float = 0.025,
    min_piece_pixels: int = 48,
    max_pieces: int = 16,
    background_tolerance: int = 18,
) -> list[tuple[tuple[int, int, int, int], Any]]:
    mask = _ink_mask(image, background_tolerance)
    bounds = _content_bounds(mask)
    if bounds is None:
        return []
    margin = 2
    initial = (
        max(0, bounds[0] - margin),
        max(0, bounds[1] - margin),
        min(image.width, bounds[2] + margin),
        min(image.height, bounds[3] + margin),
    )
    boxes = [initial]
    while len(boxes) < max_pieces:
        selected_index: int | None = None
        selected_separator: tuple[str, int, int] | None = None
        selected_area = 0
        for index, box in enumerate(boxes):
            separator = _best_separator(
                mask,
                box,
                min_gap_ratio=min_gap_ratio,
                min_piece_pixels=min_piece_pixels,
            )
            area = (box[2] - box[0]) * (box[3] - box[1])
            if separator is not None and area > selected_area:
                selected_index = index
                selected_separator = separator
                selected_area = area
        if selected_index is None or selected_separator is None:
            break
        left, top, right, bottom = boxes.pop(selected_index)
        axis, gap_start, gap_end = selected_separator
        if axis == "vertical":
            boxes.extend(((left, top, gap_start, bottom), (gap_end, top, right, bottom)))
        else:
            boxes.extend(((left, top, right, gap_start), (left, gap_end, right, bottom)))
    if len(boxes) == 1:
        return [((0, 0, image.width, image.height), image.copy())]
    boxes.sort(key=lambda item: (item[1], item[0]))
    return [(box, image.crop(box)) for box in boxes]


def _common_split_axis(pieces: list[tuple[tuple[int, int, int, int], Any]]) -> str | None:
    if len(pieces) < 2:
        return None
    boxes = [item[0] for item in pieces]
    x_positions = {box[0] for box in boxes}
    y_positions = {box[1] for box in boxes}
    if len(x_positions) > 1 and len(y_positions) == 1:
        return "vertical"
    if len(y_positions) > 1 and len(x_positions) == 1:
        return "horizontal"
    return "mixed"


def segment_pdf_images(
    source: str | Path,
    output_directory: str | Path,
    *,
    start_page: int = 1,
    end_page: int | None = None,
    max_per_page: int = 50,
    max_pieces_per_image: int = 16,
    min_gap_ratio: float = 0.025,
    overwrite: bool = False,
) -> ImageSegmentationSummary:
    if not 1 <= max_per_page <= 200:
        raise ValueError("max_per_page must be between 1 and 200.")
    if not 1 <= max_pieces_per_image <= 64:
        raise ValueError("max_pieces_per_image must be between 1 and 64.")
    if not 0.005 <= min_gap_ratio <= 0.25:
        raise ValueError("min_gap_ratio must be between 0.005 and 0.25.")

    target = Path(output_directory).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise FileExistsError(f"Image output directory is not empty: {target}")
    if target.exists() and not any(target.iterdir()):
        target.rmdir()
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        regions = extract_image_regions(
            source,
            start_page=start_page,
            end_page=end_page,
            max_per_page=max_per_page,
        )
        summary = ImageSegmentationSummary(
            status="completed",
            output_directory=str(target),
            image_count=len(regions),
        )
        for region in regions:
            result = ImageResult(
                page=region.page,
                index=region.index,
                pdf_bbox=list(region.bbox),
                source_width=0,
                source_height=0,
                status="failed",
            )
            try:
                image = _open_rgb(region.image)
                result.source_width, result.source_height = image.size
                pieces = split_image(
                    image,
                    min_gap_ratio=min_gap_ratio,
                    max_pieces=max_pieces_per_image,
                )
                if not pieces:
                    result.status = "skipped"
                    result.reason = "The image contained no detectable foreground content."
                    summary.skipped_count += 1
                    summary.results.append(result)
                    continue
                result.status = "split" if len(pieces) > 1 else "exported"
                result.split_axis = _common_split_axis(pieces)
                if len(pieces) > 1:
                    summary.split_image_count += 1
                for piece_index, (pixel_bbox, piece) in enumerate(pieces, start=1):
                    filename = (
                        f"page-{region.page:04d}_image-{region.index:03d}_"
                        f"piece-{piece_index:02d}.png"
                    )
                    piece.save(staging / filename, format="PNG")
                    result.pieces.append(
                        ImagePiece(
                            index=piece_index,
                            file=filename,
                            pixel_bbox=list(pixel_bbox),
                            width=piece.width,
                            height=piece.height,
                        )
                    )
                    summary.piece_count += 1
            except Exception as exc:  # noqa: BLE001 - isolate malformed PDF images.
                result.reason = str(exc)
                summary.failed_count += 1
            summary.results.append(result)
        if not regions:
            summary.status = "no_images"
            summary.warnings.append("No exportable PDF image regions were found.")
        elif summary.failed_count or summary.skipped_count:
            summary.status = "completed_with_warnings"

        if target.exists():
            if not overwrite:
                raise FileExistsError(f"Image output directory already exists: {target}")
            backup = Path(tempfile.mkdtemp(prefix=f".{target.name}-backup-", dir=target.parent))
            backup.rmdir()
            os.replace(target, backup)
            try:
                os.replace(staging, target)
            except Exception:
                os.replace(backup, target)
                raise
            shutil.rmtree(backup, ignore_errors=True)
        else:
            os.replace(staging, target)
        return summary
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
