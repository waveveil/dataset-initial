import torch
import numpy as np
from PIL import Image
from pathlib import Path
import open_clip

from .config import CLIP_MODEL_NAME, CLIP_PRETRAINED, BATCH_SIZE, DEVICE

_model = None
_tokenizer = None
_preprocess = None


def _get_model():
    global _model, _tokenizer, _preprocess
    if _model is None:
        _model, _, _preprocess = open_clip.create_model_and_transforms(
            CLIP_MODEL_NAME, pretrained=CLIP_PRETRAINED
        )
        _model = _model.to(DEVICE).eval()
        _tokenizer = open_clip.get_tokenizer(CLIP_MODEL_NAME)
    return _model, _preprocess, _tokenizer


def load_images(image_paths: list[Path]) -> list[tuple[Path, Image.Image]]:
    pairs = []
    for p in image_paths:
        try:
            img = Image.open(p).convert("RGB")
            pairs.append((p, img))
        except Exception:
            continue
    return pairs


@torch.no_grad()
def filter_by_scene(
    image_dir: str,
    scene_description: str,
    top_k: int = 50,
    threshold: float | None = None,
) -> list[dict]:
    model, preprocess, tokenizer = _get_model()
    image_dir = Path(image_dir)
    image_files = sorted(
        [f for f in image_dir.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    )
    if not image_files:
        return []

    text_tokens = tokenizer([scene_description]).to(DEVICE)
    text_features = model.encode_text(text_tokens)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    results = []
    for i in range(0, len(image_files), BATCH_SIZE):
        batch_paths = image_files[i : i + BATCH_SIZE]
        pairs = load_images(batch_paths)
        if not pairs:
            continue
        paths, imgs = zip(*pairs)
        image_tensors = torch.stack([preprocess(img) for img in imgs]).to(DEVICE)
        image_features = model.encode_image(image_tensors)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        similarities = (image_features @ text_features.T).squeeze(1).cpu().numpy()
        for p, sim in zip(paths, similarities):
            results.append({"path": str(p), "score": float(sim)})

    results.sort(key=lambda x: x["score"], reverse=True)
    if threshold is not None:
        results = [r for r in results if r["score"] >= threshold]
    return results[:top_k]
