import os
import tempfile
import imagehash
import numpy as np
import torch
from PIL import Image
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from sklearn.cluster import MiniBatchKMeans
from torchvision import models, transforms

from .config import BATCH_SIZE, DEVICE, OUTPUT_DIR

_feature_model = None
_feature_transform = None

MEMORY_CHUNK = 2048  # images per chunk for MiniBatchKMeans partial_fit


def _get_feature_model():
    global _feature_model, _feature_transform
    if _feature_model is None:
        weights = models.ResNet50_Weights.IMAGENET1K_V2
        _feature_model = models.resnet50(weights=weights)
        _feature_model.fc = torch.nn.Identity()
        _feature_model = _feature_model.to(DEVICE).eval()
        _feature_transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
    return _feature_model, _feature_transform


def compute_phash(img_path: str):
    try:
        img = Image.open(img_path).convert("L")
        if min(img.size) < 32:
            return None
        return imagehash.phash(img)
    except Exception:
        return None


def hamming_distance(h1, h2) -> int:
    if h1 is None or h2 is None:
        return 999
    return int(h1 - h2)


def phash_dedup(image_paths: list[str], threshold: int = 8) -> list[str]:
    # parallel pHash computation — big win for 10k+ images
    hashes = [None] * len(image_paths)
    workers = min(16, len(image_paths))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(compute_phash, p): i for i, p in enumerate(image_paths)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                hashes[idx] = future.result()
            except Exception:
                hashes[idx] = None

    retain = [image_paths[0]]
    last_hash = hashes[0]
    for i in range(1, len(image_paths)):
        dist = hamming_distance(last_hash, hashes[i])
        if dist >= threshold:
            retain.append(image_paths[i])
            last_hash = hashes[i]
    return retain


@torch.no_grad()
def _extract_features_to_memmap(image_paths: list[str], mmap_path: str) -> np.memmap:
    """Extract features and write directly to a memory-mapped file. RAM constant regardless of dataset size."""
    model, transform = _get_feature_model()
    n = len(image_paths)
    mmap = np.memmap(mmap_path, dtype=np.float32, mode='w+', shape=(n, 2048))

    for i in range(0, n, BATCH_SIZE):
        batch_paths = image_paths[i: i + BATCH_SIZE]
        tensors = []
        valid_indices = []
        for j, p in enumerate(batch_paths):
            try:
                img = Image.open(p).convert("RGB")
                tensors.append(transform(img))
                valid_indices.append(i + j)
            except Exception:
                continue
        if not tensors:
            mmap[i: i + BATCH_SIZE] = 0.0
            continue
        stacked = torch.stack(tensors).to(DEVICE)
        feats = model(stacked).cpu().numpy().astype(np.float32)
        for vi, f in zip(valid_indices, feats):
            mmap[vi] = f
        # failed rows stay as zeros

    mmap.flush()
    return mmap


def diversity_sample_by_kmeans(
    image_paths: list[str], target_count: int
) -> list[str]:
    if len(image_paths) <= target_count:
        return image_paths

    fd, mmap_path = tempfile.mkstemp(suffix=".dat", dir=str(OUTPUT_DIR))
    os.close(fd)
    mmap = None

    try:
        mmap = _extract_features_to_memmap(image_paths, mmap_path)
        n = len(image_paths)

        # normalize rows for cosine-like distance
        norms = np.linalg.norm(mmap, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        for start in range(0, n, MEMORY_CHUNK):
            end = min(start + MEMORY_CHUNK, n)
            mmap[start:end] /= norms[start:end]

        # MiniBatchKMeans: partial_fit in chunks, never holds full dataset in RAM.
        # chunk size must be >= n_clusters for partial_fit to pass validation.
        fit_chunk = max(MEMORY_CHUNK, target_count)
        kmeans = MiniBatchKMeans(
            n_clusters=target_count,
            random_state=42,
            batch_size=min(MEMORY_CHUNK, n),
            n_init=3,
        )
        for start in range(0, n, fit_chunk):
            end = min(start + fit_chunk, n)
            chunk = np.array(mmap[start:end])
            kmeans.partial_fit(chunk)

        labels = np.empty(n, dtype=np.int32)
        for start in range(0, n, MEMORY_CHUNK):
            end = min(start + MEMORY_CHUNK, n)
            chunk = np.array(mmap[start:end])
            labels[start:end] = kmeans.predict(chunk)

        centers = kmeans.cluster_centers_

        selected = []
        for cluster_idx in range(target_count):
            members = [j for j, lbl in enumerate(labels) if lbl == cluster_idx]
            if not members:
                continue
            member_feats = np.array(mmap[members])
            center = centers[cluster_idx]
            dists = np.linalg.norm(member_feats - center, axis=1)
            nearest = members[int(np.argmin(dists))]
            selected.append(nearest)

        selected.sort()
        return [image_paths[i] for i in selected]

    finally:
        if mmap is not None:
            del mmap
        try:
            os.remove(mmap_path)
        except OSError:
            pass


def dedup_and_sample(
    image_dir: str,
    target_count: int = 50,
    phash_threshold: int = 8,
) -> list[dict]:
    image_dir = Path(image_dir)
    image_files = sorted(
        [str(f) for f in image_dir.iterdir()
         if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    )
    if not image_files:
        return []

    after_dedup = phash_dedup(image_files, threshold=phash_threshold)

    sampled = diversity_sample_by_kmeans(after_dedup, target_count)

    return [
        {
            "path": p,
            "stage": "sampled",
            "total_input": len(image_files),
            "after_dedup": len(after_dedup),
            "after_sample": len(sampled),
        }
        for p in sampled
    ]
