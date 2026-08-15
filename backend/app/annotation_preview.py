import io
import math
import os
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 100_000_000

from .dataset_stats import SUPPORTED_IMAGE_EXTS, parse_yolo_label


SESSION_TTL_SECONDS = 30 * 60
MAX_PREVIEW_SESSIONS = 32

BOX_COLORS = (
    "#3b82f6", "#22c55e", "#f97316", "#e879f9", "#06b6d4",
    "#f43f5e", "#eab308", "#8b5cf6", "#14b8a6", "#fb7185",
)


class PreviewValidationError(ValueError):
    pass


class PreviewSessionNotFound(LookupError):
    pass


class PreviewImageNotFound(LookupError):
    pass


class PreviewRenderError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreviewImage:
    image_id: str
    name: str
    path: Path
    label_path: Path | None

    def as_dict(self) -> dict:
        return {
            "id": self.image_id,
            "name": self.name,
            "has_label": self.label_path is not None,
        }


@dataclass
class PreviewSession:
    session_id: str
    image_dir: Path
    label_dir: Path
    images: dict[str, PreviewImage]
    last_access: float


@dataclass(frozen=True)
class RenderedPreview:
    content: bytes
    label_found: bool
    box_count: int
    skipped_count: int


class PreviewSessionStore:
    def __init__(
        self,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        max_sessions: int = MAX_PREVIEW_SESSIONS,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, PreviewSession] = OrderedDict()
        self._lock = RLock()

    def create(self, image_dir: str, label_dir: str) -> dict:
        image_root = _resolve_directory(image_dir, "图片文件夹")
        label_root = _resolve_directory(label_dir, "标签文件夹")

        image_paths = sorted(
            (
                path.resolve()
                for path in image_root.iterdir()
                if path.is_file()
                and path.suffix.lower() in SUPPORTED_IMAGE_EXTS
                and _is_within(path.resolve(), image_root)
            ),
            key=lambda path: (path.name.casefold(), path.name),
        )
        if not image_paths:
            raise PreviewValidationError("图片文件夹中没有支持的图片文件")

        records: list[PreviewImage] = []
        for image_path in image_paths:
            label_candidate = label_root / f"{image_path.stem}.txt"
            resolved_label = None
            if label_candidate.is_file():
                candidate = label_candidate.resolve()
                if _is_within(candidate, label_root):
                    resolved_label = candidate

            records.append(PreviewImage(
                image_id=uuid.uuid4().hex,
                name=image_path.name,
                path=image_path,
                label_path=resolved_label,
            ))

        now = time.monotonic()
        session_id = uuid.uuid4().hex
        session = PreviewSession(
            session_id=session_id,
            image_dir=image_root,
            label_dir=label_root,
            images={record.image_id: record for record in records},
            last_access=now,
        )

        with self._lock:
            self._remove_expired(now)
            while len(self._sessions) >= self.max_sessions:
                self._sessions.popitem(last=False)
            self._sessions[session_id] = session

        return {
            "session_id": session_id,
            "images": [record.as_dict() for record in records],
            "total": len(records),
            "missing_labels": sum(record.label_path is None for record in records),
        }

    def get_image(self, session_id: str, image_id: str) -> PreviewImage:
        now = time.monotonic()
        with self._lock:
            self._remove_expired(now)
            session = self._sessions.get(session_id)
            if session is None:
                raise PreviewSessionNotFound("预览会话不存在或已过期，请重新加载目录")

            image = session.images.get(image_id)
            if image is None:
                raise PreviewImageNotFound("所选图片不属于当前预览会话")

            session.last_access = now
            self._sessions.move_to_end(session_id)
            return image

    def clear(self):
        with self._lock:
            self._sessions.clear()

    def _remove_expired(self, now: float):
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_access > self.ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)


preview_sessions = PreviewSessionStore()


def create_preview_session(image_dir: str, label_dir: str) -> dict:
    return preview_sessions.create(image_dir, label_dir)


def render_preview(
    session_id: str,
    image_id: str,
    class_mapping_text: str = "",
) -> RenderedPreview:
    class_names = parse_class_mapping(class_mapping_text)
    image_record = preview_sessions.get_image(session_id, image_id)
    return _render_image(image_record, class_names)


def parse_class_mapping(mapping_text: str) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for line_number, raw_line in enumerate(mapping_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        if ":" in line:
            raw_id, raw_name = line.split(":", 1)
        elif "：" in line:
            raw_id, raw_name = line.split("：", 1)
        else:
            raise PreviewValidationError(
                f"类别映射第 {line_number} 行缺少冒号，应写成 ID:类别名称"
            )

        raw_id = raw_id.strip()
        class_name = raw_name.strip()
        if not raw_id:
            raise PreviewValidationError(f"类别映射第 {line_number} 行缺少类别 ID")
        if not class_name:
            raise PreviewValidationError(f"类别映射第 {line_number} 行缺少类别名称")

        try:
            class_id = int(raw_id)
        except ValueError as exc:
            raise PreviewValidationError(
                f"类别映射第 {line_number} 行的 ID 必须是整数"
            ) from exc
        if class_id < 0:
            raise PreviewValidationError(
                f"类别映射第 {line_number} 行的 ID 不能是负数"
            )
        if class_id in mapping:
            raise PreviewValidationError(f"类别 ID {class_id} 重复")
        mapping[class_id] = class_name

    return mapping


def _resolve_directory(raw_path: str, field_name: str) -> Path:
    if not raw_path or not raw_path.strip():
        raise PreviewValidationError(f"请提供{field_name}路径")

    path = Path(raw_path.strip()).expanduser()
    if not path.is_dir():
        raise PreviewValidationError(f"{field_name}不存在")
    return path.resolve()


def _is_within(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _render_image(
    image_record: PreviewImage,
    class_names: dict[int, str],
) -> RenderedPreview:
    try:
        with Image.open(image_record.path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise PreviewRenderError(f"无法读取图片：{image_record.name}") from exc

    boxes = []
    skipped_count = 0
    if image_record.label_path is not None:
        nonempty_lines = _count_nonempty_lines(image_record.label_path)
        boxes = parse_yolo_label(str(image_record.label_path))
        skipped_count = max(0, nonempty_lines - len(boxes))

    draw = ImageDraw.Draw(image)
    font = _load_font(image.size)
    line_width = max(2, min(image.size) // 300)
    box_count = 0

    for box in boxes:
        bounds = _box_to_pixels(box, image.width, image.height)
        if bounds is None:
            skipped_count += 1
            continue

        class_id = box["class_id"]
        if class_id < 0:
            skipped_count += 1
            continue
        color = BOX_COLORS[class_id % len(BOX_COLORS)]
        draw.rectangle(bounds, outline=color, width=line_width)
        label = class_names.get(class_id, str(class_id))
        _draw_label(draw, bounds, label, str(class_id), color, font, image.size)
        box_count += 1

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return RenderedPreview(
        content=output.getvalue(),
        label_found=image_record.label_path is not None,
        box_count=box_count,
        skipped_count=skipped_count,
    )


def _count_nonempty_lines(label_path: Path) -> int:
    try:
        with label_path.open("r", encoding="utf-8-sig", errors="replace") as file:
            return sum(1 for line in file if line.strip())
    except OSError as exc:
        raise PreviewRenderError(f"无法读取标签文件：{label_path.name}") from exc


def _box_to_pixels(box: dict, image_width: int, image_height: int):
    values = (box["cx"], box["cy"], box["w"], box["h"])
    if not all(math.isfinite(value) for value in values):
        return None

    cx, cy, width, height = values
    if width <= 0 or height <= 0:
        return None

    left = (cx - width / 2) * image_width
    top = (cy - height / 2) * image_height
    right = (cx + width / 2) * image_width
    bottom = (cy + height / 2) * image_height

    if right <= 0 or bottom <= 0 or left >= image_width or top >= image_height:
        return None

    left = max(0, min(image_width - 1, round(left)))
    top = max(0, min(image_height - 1, round(top)))
    right = max(0, min(image_width - 1, round(right)))
    bottom = max(0, min(image_height - 1, round(bottom)))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _load_font(image_size: tuple[int, int]):
    font_size = max(12, min(36, round(min(image_size) * 0.035)))
    windows_dir = Path(os.environ.get("WINDIR", "C:/Windows"))
    candidates = (
        windows_dir / "Fonts" / "msyh.ttc",
        windows_dir / "Fonts" / "simhei.ttf",
        windows_dir / "Fonts" / "arial.ttf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            return ImageFont.truetype(str(candidate), font_size)
        except OSError:
            continue

    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def _draw_label(
    draw: ImageDraw.ImageDraw,
    bounds,
    label: str,
    fallback_label: str,
    color: str,
    font,
    image_size: tuple[int, int],
):
    try:
        _draw_label_text(draw, bounds, label, color, font, image_size)
    except (UnicodeEncodeError, OSError):
        _draw_label_text(draw, bounds, fallback_label, color, font, image_size)


def _draw_label_text(
    draw: ImageDraw.ImageDraw,
    bounds,
    label: str,
    color: str,
    font,
    image_size: tuple[int, int],
):
    padding = 3
    text_bounds = draw.textbbox((0, 0), label, font=font)
    text_width = text_bounds[2] - text_bounds[0]
    text_height = text_bounds[3] - text_bounds[1]
    background_width = text_width + padding * 2
    background_height = text_height + padding * 2

    image_width, image_height = image_size
    left, top, _, _ = bounds
    label_x = max(0, min(left, image_width - background_width))
    label_y = top - background_height
    if label_y < 0:
        label_y = min(top, image_height - background_height)

    background = (
        label_x,
        label_y,
        min(image_width - 1, label_x + background_width),
        min(image_height - 1, label_y + background_height),
    )
    draw.rectangle(background, fill=color)
    draw.text(
        (label_x + padding - text_bounds[0], label_y + padding - text_bounds[1]),
        label,
        fill="white",
        font=font,
    )
