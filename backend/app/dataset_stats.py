import io
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ── label parsing ────────────────────────────────────────────────────────────

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# COCO-style size thresholds (relative area, assuming normalized coords 0–1)
# For a 640×640 image: small < 32² ≈ 0.0025, medium 32²–96² ≈ 0.0025–0.0225
SMALL_THRESHOLD = 0.0025
LARGE_THRESHOLD = 0.0225


def parse_yolo_label(file_path: str) -> list[dict]:
    """Parse a YOLO-format label file.

    Each line:  class_id  cx  cy  w  h   (normalized 0–1)
    Returns list of {class_id, cx, cy, w, h, area}.
    """
    boxes = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                try:
                    cls_id = int(parts[0])
                    cx = float(parts[1])
                    cy = float(parts[2])
                    w = float(parts[3])
                    h = float(parts[4])
                except ValueError:
                    continue
                boxes.append({
                    "class_id": cls_id,
                    "cx": cx, "cy": cy,
                    "w": w, "h": h,
                    "area": w * h,
                })
    except Exception:
        pass
    return boxes


def parse_voc_label(file_path: str) -> list[dict]:
    """Parse a Pascal VOC XML label file.

    Bounding boxes are in absolute pixels; image dimensions are read from
    <size>/<width>,<height> so boxes can be normalised to 0–1.
    """
    boxes = []
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        size = root.find("size")
        img_w = float(size.find("width").text) if size is not None and size.find("width") is not None else None
        img_h = float(size.find("height").text) if size is not None and size.find("height") is not None else None

        for obj in root.findall("object"):
            name_el = obj.find("name")
            cls_name = name_el.text.strip() if name_el is not None and name_el.text else ""
            bndbox = obj.find("bndbox")
            if bndbox is None:
                continue
            xmin = float(bndbox.find("xmin").text)
            ymin = float(bndbox.find("ymin").text)
            xmax = float(bndbox.find("xmax").text)
            ymax = float(bndbox.find("ymax").text)

            bw = xmax - xmin
            bh = ymax - ymin
            if img_w and img_h:
                cx = ((xmin + xmax) / 2) / img_w
                cy = ((ymin + ymax) / 2) / img_h
                w = bw / img_w
                h = bh / img_h
            else:
                # fallback: treat as normalised (unlikely for VOC, but safe)
                cx = (xmin + xmax) / 2
                cy = (ymin + ymax) / 2
                w = bw
                h = bh

            boxes.append({
                "class_id": cls_name,
                "cx": cx, "cy": cy,
                "w": w, "h": h,
                "area": w * h,
            })
    except Exception:
        pass
    return boxes


def _scan_label_files(label_dir: str, label_ext: str) -> list[str]:
    """Return all label files in label_dir, sorted."""
    lbl_dir = Path(label_dir)
    if not lbl_dir.is_dir():
        return []
    ext = label_ext if label_ext.startswith(".") else f".{label_ext}"
    return sorted(str(f) for f in lbl_dir.iterdir() if f.suffix == ext)


def _cross_check_images(image_dir: str, label_dir: str, label_ext: str) -> dict:
    """Cross-reference images and labels, without filtering label files."""
    img_dir = Path(image_dir)
    lbl_dir = Path(label_dir)
    ext = label_ext if label_ext.startswith(".") else f".{label_ext}"

    image_files = sorted(
        f for f in img_dir.iterdir()
        if f.suffix.lower() in SUPPORTED_IMAGE_EXTS
    )
    image_stems = {f.stem for f in image_files}
    label_stems = {f.stem for f in lbl_dir.iterdir() if f.suffix == ext}

    matched = image_stems & label_stems
    return {
        "total_images_in_dir": len(image_files),
        "images_with_labels": len(matched),
        "images_without_labels": len(image_stems - label_stems),
        "labels_without_images": len(label_stems - image_stems),
    }


def _classify_size(area: float) -> str:
    if area < SMALL_THRESHOLD:
        return "small"
    if area < LARGE_THRESHOLD:
        return "medium"
    return "large"


# ── statistics ───────────────────────────────────────────────────────────────

def compute_stats(label_dir: str, label_format: str = "txt", image_dir: str | None = None) -> dict:
    """Compute dataset statistics from label files and generate charts.

    Statistics are always based on ALL label files in the directory.
    If image_dir is provided, additional image-label cross-reference info
    is appended but does not alter the core label statistics.
    """
    ext = label_format if label_format.startswith(".") else f".{label_format}"
    label_files = _scan_label_files(label_dir, ext)
    if not label_files:
        return {"error": f"标签文件夹中没有 {ext} 文件", "total_images": 0}

    parser = parse_yolo_label if label_format in ("txt", ".txt") else parse_voc_label

    all_boxes: list[dict] = []
    image_box_counts: list[int] = []
    class_counter: Counter = Counter()
    size_counter: Counter = Counter()

    for lf in label_files:
        boxes = parser(lf)
        image_box_counts.append(len(boxes))
        for box in boxes:
            box["label_stem"] = Path(lf).stem
            all_boxes.append(box)
            class_counter[str(box["class_id"])] += 1
            size_counter[_classify_size(box["area"])] += 1

    total_labels = len(label_files)
    total_targets = len(all_boxes)

    if total_targets == 0:
        result = {
            "total_labels": total_labels,
            "total_targets": 0,
            "targets_per_label_avg": 0.0,
            "targets_per_label_min": 0,
            "targets_per_label_max": 0,
            "class_counts": {},
            "size_distribution": {"small": 0, "medium": 0, "large": 0},
            "size_percentages": {"small": 0.0, "medium": 0.0, "large": 0.0},
            "charts": {},
        }
        if image_dir:
            result["cross_check"] = _cross_check_images(image_dir, label_dir, ext)
        return result

    targets_per_label = np.array(image_box_counts, dtype=np.int32)

    sorted_classes = sorted(class_counter.items(), key=lambda x: x[0])
    class_counts = dict(sorted_classes)

    size_dist = {
        "small": size_counter.get("small", 0),
        "medium": size_counter.get("medium", 0),
        "large": size_counter.get("large", 0),
    }

    charts = {}
    boxes_arr = _boxes_to_array(all_boxes)
    class_ids_for_plots = [b["class_id"] for b in all_boxes]

    charts["labels"] = _make_labels_chart(
        class_counts, targets_per_label, boxes_arr, class_ids_for_plots
    )
    charts["correlogram"] = _make_correlogram(boxes_arr)

    stats = {
        "total_labels": total_labels,
        "total_targets": total_targets,
        "targets_per_label_avg": round(float(targets_per_label.mean()), 2),
        "targets_per_label_median": round(float(np.median(targets_per_label)), 2),
        "targets_per_label_min": int(targets_per_label.min()),
        "targets_per_label_max": int(targets_per_label.max()),
        "class_counts": class_counts,
        "num_classes": len(class_counts),
        "size_distribution": size_dist,
        "size_percentages": {
            k: round(v / total_targets * 100, 1) if total_targets > 0 else 0.0
            for k, v in size_dist.items()
        },
        "charts": charts,
    }

    if image_dir:
        stats["cross_check"] = _cross_check_images(image_dir, label_dir, ext)

    return stats


def _boxes_to_array(boxes: list[dict]) -> np.ndarray:
    """Extract cx, cy, w, h as (N, 4) float array."""
    data = np.array([[b["cx"], b["cy"], b["w"], b["h"]] for b in boxes], dtype=np.float32)
    return data


# ── chart generation ─────────────────────────────────────────────────────────

DARK_BG = "#1a1a2e"
GRID_COLOR = "#333355"
TEXT_COLOR = "#e0e0e0"
SCATTER_ALPHA = 0.35
SCATTER_S = 3


def _make_labels_chart(
    class_counts: dict,
    targets_per_image: np.ndarray,
    boxes_arr: np.ndarray,
    class_ids: list,
) -> str:
    """Generate Ultralytics-style labels.jpg (2×2 grid)."""
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), facecolor=DARK_BG)
    fig.subplots_adjust(hspace=0.35, wspace=0.30)

    cmap = plt.get_cmap("tab20")

    # ── subplot 1: class distribution (horizontal bars) ──
    ax1 = axes[0, 0]
    ax1.set_facecolor(DARK_BG)
    classes = list(class_counts.keys())
    counts = list(class_counts.values())
    y_pos = range(len(classes))
    colors = [cmap(i % 20) for i in range(len(classes))]
    ax1.barh(y_pos, counts, color=colors, height=0.7)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(classes, fontsize=8, color=TEXT_COLOR)
    ax1.invert_yaxis()
    ax1.set_xlabel("instances", color=TEXT_COLOR, fontsize=9)
    ax1.set_title("Class Distribution", color=TEXT_COLOR, fontsize=11, fontweight="bold")
    ax1.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_color(GRID_COLOR)
    ax1.spines["bottom"].set_color(GRID_COLOR)
    ax1.grid(axis="x", color=GRID_COLOR, alpha=0.4, linewidth=0.5)

    # ── subplot 2: instances per image histogram ──
    ax2 = axes[0, 1]
    ax2.set_facecolor(DARK_BG)
    max_instances = int(targets_per_image.max()) if len(targets_per_image) > 0 else 0
    bins = min(max(1, max_instances), 60)
    ax2.hist(targets_per_image, bins=bins, color="#4ecdc4", edgecolor=DARK_BG, alpha=0.85, rwidth=0.9)
    ax2.set_xlabel("instances", color=TEXT_COLOR, fontsize=9)
    ax2.set_ylabel("images", color=TEXT_COLOR, fontsize=9)
    ax2.set_title("Instances per Image", color=TEXT_COLOR, fontsize=11, fontweight="bold")
    ax2.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_color(GRID_COLOR)
    ax2.spines["bottom"].set_color(GRID_COLOR)
    ax2.grid(color=GRID_COLOR, alpha=0.4, linewidth=0.5)

    # ── subplot 3: bbox width vs height scatter ──
    ax3 = axes[1, 0]
    ax3.set_facecolor(DARK_BG)
    if boxes_arr.shape[0] > 0:
        unique_cls = sorted(set(class_ids), key=str)
        cls_to_idx = {c: i for i, c in enumerate(unique_cls)}
        for c in unique_cls:
            mask = [cls_id == c for cls_id in class_ids]
            idx = cls_to_idx[c] % 20
            ax3.scatter(
                boxes_arr[mask, 2], boxes_arr[mask, 3],
                s=SCATTER_S, alpha=SCATTER_ALPHA,
                color=cmap(idx), label=str(c), edgecolors="none",
            )
    ax3.set_xlabel("width", color=TEXT_COLOR, fontsize=9)
    ax3.set_ylabel("height", color=TEXT_COLOR, fontsize=9)
    ax3.set_title("bbox width × height", color=TEXT_COLOR, fontsize=11, fontweight="bold")
    ax3.set_xlim(-0.02, 1.02)
    ax3.set_ylim(-0.02, 1.02)
    ax3.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)
    ax3.spines["left"].set_color(GRID_COLOR)
    ax3.spines["bottom"].set_color(GRID_COLOR)
    ax3.grid(color=GRID_COLOR, alpha=0.4, linewidth=0.5)
    if len(unique_cls) <= 10:
        ax3.legend(fontsize=7, labelcolor=TEXT_COLOR, facecolor=DARK_BG,
                   edgecolor=GRID_COLOR, markerscale=3)

    # ── subplot 4: bbox center (x, y) scatter ──
    ax4 = axes[1, 1]
    ax4.set_facecolor(DARK_BG)
    if boxes_arr.shape[0] > 0:
        for c in unique_cls:
            mask = [cls_id == c for cls_id in class_ids]
            idx = cls_to_idx[c] % 20
            ax4.scatter(
                boxes_arr[mask, 0], boxes_arr[mask, 1],
                s=SCATTER_S, alpha=SCATTER_ALPHA,
                color=cmap(idx), label=str(c), edgecolors="none",
            )
    ax4.set_xlabel("x", color=TEXT_COLOR, fontsize=9)
    ax4.set_ylabel("y", color=TEXT_COLOR, fontsize=9)
    ax4.set_title("bbox xy center", color=TEXT_COLOR, fontsize=11, fontweight="bold")
    ax4.set_xlim(-0.02, 1.02)
    ax4.set_ylim(-0.02, 1.02)
    ax4.tick_params(colors=TEXT_COLOR, labelsize=7)
    ax4.spines["top"].set_visible(False)
    ax4.spines["right"].set_visible(False)
    ax4.spines["left"].set_color(GRID_COLOR)
    ax4.spines["bottom"].set_color(GRID_COLOR)
    ax4.grid(color=GRID_COLOR, alpha=0.4, linewidth=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _make_correlogram(boxes_arr: np.ndarray) -> str:
    """Generate Ultralytics-style labels_correlogram.jpg (4×4 pairwise)."""
    names = ["x", "y", "width", "height"]
    n = len(names)

    fig, axes = plt.subplots(n, n, figsize=(10, 10), facecolor=DARK_BG)
    fig.subplots_adjust(hspace=0.30, wspace=0.30)

    for row in range(n):
        for col in range(n):
            ax = axes[row, col]
            ax.set_facecolor(DARK_BG)

            if row == col:
                # diagonal: histogram
                data = boxes_arr[:, row] if boxes_arr.shape[0] > 0 else []
                ax.hist(data, bins=40, color="#4ecdc4", edgecolor=DARK_BG, alpha=0.85)
                ax.set_xlim(-0.02, 1.02)
            else:
                # off-diagonal: scatter
                if boxes_arr.shape[0] > 0:
                    ax.scatter(
                        boxes_arr[:, col], boxes_arr[:, row],
                        s=SCATTER_S * 0.7, alpha=SCATTER_ALPHA,
                        color="#ff6b6b", edgecolors="none",
                    )
                ax.set_xlim(-0.02, 1.02)
                ax.set_ylim(-0.02, 1.02)

            if row == n - 1:
                ax.set_xlabel(names[col], color=TEXT_COLOR, fontsize=8)
            if col == 0:
                ax.set_ylabel(names[row], color=TEXT_COLOR, fontsize=8)

            ax.tick_params(colors=TEXT_COLOR, labelsize=6)
            for spine in ax.spines.values():
                spine.set_color(GRID_COLOR)
            ax.grid(color=GRID_COLOR, alpha=0.3, linewidth=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=DARK_BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
