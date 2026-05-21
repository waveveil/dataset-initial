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
from torch.utils.data import Dataset, DataLoader

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


class ImagePathDataset(Dataset):
    def __init__(self, image_paths: list[str], transform):
        self.paths = image_paths
        self.transform = transform

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        try:
            img = Image.open(self.paths[idx]).convert("RGB")
            return self.transform(img), idx, True
        except Exception:
            return torch.zeros(3, 224, 224), idx, False


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
    model, transform = _get_feature_model()
    n = len(image_paths)
    mmap = np.memmap(mmap_path, dtype=np.float32, mode='w+', shape=(n, 2048))

    gpu_batch = 128 if DEVICE == "cuda" else BATCH_SIZE
    num_workers = 4 if DEVICE == "cuda" else 0

    dataset = ImagePathDataset(image_paths, transform)
    loader = DataLoader(
        dataset,
        batch_size=gpu_batch,
        num_workers=num_workers,
        pin_memory=(DEVICE == "cuda"),
        shuffle=False,
    )

    for batch_tensors, batch_indices, batch_ok in loader:
        valid_mask = batch_ok.numpy().astype(bool)
        if not valid_mask.any():
            continue

        batch_tensors = batch_tensors.to(DEVICE)
        if DEVICE == "cuda":
            with torch.autocast(device_type="cuda"):
                feats = model(batch_tensors)
        else:
            feats = model(batch_tensors)
        feats = feats.cpu().numpy().astype(np.float32)

        for j, ok in enumerate(valid_mask):
            row = batch_indices[j].item()
            if ok:
                mmap[row] = feats[j]
            else:
                mmap[row] = 0.0

    mmap.flush()
    return mmap


def _uniform_sample(image_paths: list[str], target_count: int) -> list[str]:
    if len(image_paths) <= target_count:
        return image_paths
    step = len(image_paths) / target_count
    return [image_paths[int(i * step)] for i in range(target_count)]


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

        norms = np.linalg.norm(mmap, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        for start in range(0, n, MEMORY_CHUNK):
            end = min(start + MEMORY_CHUNK, n)
            mmap[start:end] /= norms[start:end]

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


def find_label_files(
    image_paths: list[str],
    label_dirs: list[str],
    extensions: tuple[str, ...] = (".txt", ".xml"),
) -> dict[str, list[str]]:
    """Match label files to images by filename stem."""
    mapping: dict[str, list[str]] = {}
    for img_path in image_paths:
        stem = Path(img_path).stem
        matched: list[str] = []
        for label_dir in label_dirs:
            label_dir_path = Path(label_dir)
            if not label_dir_path.is_dir():
                continue
            for ext in extensions:
                candidate = label_dir_path / f"{stem}{ext}"
                if candidate.is_file():
                    matched.append(str(candidate))
        if matched:
            mapping[img_path] = matched
    return mapping


def dedup_and_sample(
    image_dir: str,
    target_count: int = 50,
    phash_threshold: int = 8,
    fast_mode: bool = False,
) -> list[dict]:
    image_dir = Path(image_dir)
    image_files = sorted(
        [str(f) for f in image_dir.iterdir()
         if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}]
    )
    if not image_files:
        return []

    after_dedup = phash_dedup(image_files, threshold=phash_threshold)

    if fast_mode:
        sampled = _uniform_sample(after_dedup, target_count)
    else:
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
