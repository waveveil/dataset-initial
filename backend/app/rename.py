import shutil
from pathlib import Path


def _all_files(directory: str) -> list[Path]:
    """Return all files in directory, sorted by name (case-insensitive)."""
    p = Path(directory)
    if not p.is_dir():
        return []
    files = [f for f in p.iterdir() if f.is_file()]
    files.sort(key=lambda f: f.name.lower())
    return files


def preview_rename(
    image_dir: str,
    prefix: str = "",
    zfill: int = 0,
    output_dir: str = "",
) -> list[dict]:
    files = _all_files(image_dir)
    if not files:
        return []

    out = Path(output_dir) if output_dir else None
    plan = []
    for i, fp in enumerate(files, start=1):
        num = str(i).zfill(zfill) if zfill > 0 else str(i)
        name = f"{prefix}_{num}" if prefix else num
        new_name = f"{name}{fp.suffix}"
        new_path = str((out / new_name) if out else (fp.parent / new_name))

        plan.append({
            "old_path": str(fp),
            "old_name": fp.name,
            "new_name": new_name,
            "new_path": new_path,
        })
    return plan


def execute_rename(
    image_dir: str,
    prefix: str = "",
    zfill: int = 0,
    output_dir: str = "",
) -> list[dict]:
    plan = preview_rename(image_dir, prefix, zfill, output_dir)
    if not plan:
        return []

    out = Path(output_dir) if output_dir else None

    if out:
        out.mkdir(parents=True, exist_ok=True)
        for item in plan:
            shutil.copy2(item["old_path"], item["new_path"])
        return plan

    # in-place rename: two-step to avoid collision with existing names
    tmp_names = []
    for item in plan:
        tmp = Path(item["old_path"]).parent / f".rn_tmp_{item['new_name']}"
        shutil.move(item["old_path"], str(tmp))
        tmp_names.append((tmp, item["new_path"]))

    for tmp, final in tmp_names:
        shutil.move(str(tmp), final)

    return plan
