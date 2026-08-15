import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .config import UPLOAD_DIR, OUTPUT_DIR
from .scene_filter import filter_by_scene
from .dedup import dedup_and_sample
from .rename import preview_rename, execute_rename
from .dataset_stats import compute_stats
from .annotation_preview import (
    PreviewImageNotFound,
    PreviewRenderError,
    PreviewSessionNotFound,
    PreviewValidationError,
    create_preview_session,
    render_preview,
)


class ExportRequest(BaseModel):
    file_paths: list[str]
    output_dir: str
    label_dirs: list[str] | None = None


class AnnotationPreviewLoadRequest(BaseModel):
    image_dir: str
    label_dir: str


class AnnotationPreviewRenderRequest(BaseModel):
    session_id: str
    image_id: str
    class_mapping: str = ""


app = FastAPI(title="数据集初筛工具")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/images", StaticFiles(directory=str(UPLOAD_DIR)), name="images")


@app.get("/api/image-file")
async def serve_image_file(path: str = Query(...)):
    file_path = Path(path)
    if not file_path.is_file():
        return Response(status_code=404)
    return FileResponse(file_path)


@app.post("/api/annotations/preview/load")
async def api_annotation_preview_load(req: AnnotationPreviewLoadRequest):
    try:
        return create_preview_session(req.image_dir, req.label_dir)
    except PreviewValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="无法读取所选文件夹") from exc


@app.post("/api/annotations/preview/render")
async def api_annotation_preview_render(req: AnnotationPreviewRenderRequest):
    try:
        rendered = render_preview(
            req.session_id,
            req.image_id,
            req.class_mapping,
        )
    except PreviewValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PreviewSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PreviewImageNotFound as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PreviewRenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return Response(
        content=rendered.content,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Label-Found": str(rendered.label_found).lower(),
            "X-Box-Count": str(rendered.box_count),
            "X-Skipped-Box-Count": str(rendered.skipped_count),
            "Access-Control-Expose-Headers": (
                "X-Label-Found, X-Box-Count, X-Skipped-Box-Count"
            ),
        },
    )


@app.post("/api/filter/scene")
async def api_filter_scene(
    file: UploadFile = File(None),
    image_dir: str = Form(None),
    scene_description: str = Form(...),
    top_k: int = Form(50),
    threshold: float | None = Form(None),
):
    if image_dir:
        work_dir = Path(image_dir)
    elif file:
        work_dir = UPLOAD_DIR / str(uuid.uuid4())
        work_dir.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        import zipfile, io
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                zf.extractall(work_dir)
        except zipfile.BadZipFile:
            return {"error": "请上传 ZIP 压缩包或指定已有目录路径"}
    else:
        return {"error": "请提供图片目录路径或上传 ZIP 文件"}

    results = filter_by_scene(
        str(work_dir), scene_description, top_k=top_k, threshold=threshold
    )
    return {
        "results": results,
        "total": len(results),
        "scene_description": scene_description,
    }


@app.post("/api/dedup/sample")
async def api_dedup_sample(
    file: UploadFile = File(None),
    image_dir: str = Form(None),
    target_count: int = Form(50),
    phash_threshold: int = Form(8),
    fast_mode: bool = Form(False),
):
    if image_dir:
        work_dir = Path(image_dir)
    elif file:
        work_dir = UPLOAD_DIR / str(uuid.uuid4())
        work_dir.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        import zipfile, io
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                zf.extractall(work_dir)
        except zipfile.BadZipFile:
            return {"error": "请上传 ZIP 压缩包或指定已有目录路径"}
    else:
        return {"error": "请提供图片目录路径或上传 ZIP 文件"}

    results = dedup_and_sample(
        str(work_dir),
        target_count=target_count,
        phash_threshold=phash_threshold,
        fast_mode=fast_mode,
    )
    return {
        "results": results,
        "total": len(results),
    }


def _resolve_label_format(label_path: Path, label_dirs: list[str]) -> str:
    """Map a label file back to its source label directory and return the
    grandparent directory name as the format identifier.
    """
    label_str = str(label_path)
    for ld in label_dirs:
        if label_str.startswith(ld.rstrip("/").rstrip("\\")):
            return Path(ld).parent.name
    return label_path.parent.name


@app.post("/api/export")
async def api_export(req: ExportRequest):
    output = Path(req.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    img_dir = output / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    label_copied = 0
    for src in req.file_paths:
        src_path = Path(src)
        if src_path.exists():
            dst = img_dir / src_path.name
            shutil.copy2(src_path, dst)
            copied.append(str(dst))

    if req.label_dirs:
        from .dedup import find_label_files
        label_map = find_label_files(req.file_paths, req.label_dirs)
        for label_paths in label_map.values():
            for label_path in label_paths:
                lp = Path(label_path)
                fmt_name = _resolve_label_format(lp, req.label_dirs)
                label_out = output / "labels" / fmt_name / lp.name
                label_out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(label_path, label_out)
                label_copied += 1

    return {
        "exported": len(copied),
        "label_exported": label_copied,
        "output_dir": str(output),
    }


@app.post("/api/labels/extract")
async def api_labels_extract(
    image_dir: str = Form(...),
    label_dirs: str = Form(...),
    output_dir: str = Form(None),
):
    img_dir = Path(image_dir)
    if not img_dir.is_dir():
        return {"error": "目标图片文件夹不存在"}

    image_files = sorted([
        str(f) for f in img_dir.iterdir()
        if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    ])
    if not image_files:
        return {"error": "目标文件夹中没有图片文件"}

    parsed_label_dirs = [d.strip() for d in label_dirs.split(",") if d.strip()]
    if not parsed_label_dirs:
        return {"error": "请提供标签文件夹路径"}

    from .dedup import find_label_files
    label_map = find_label_files(image_files, parsed_label_dirs)

    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = img_dir.parent / "label"
    out_dir.mkdir(parents=True, exist_ok=True)

    details = []
    for img_path, label_paths in label_map.items():
        for lp in label_paths:
            lp_path = Path(lp)
            dst = out_dir / lp_path.name
            shutil.copy2(lp_path, dst)
            details.append({
                "image": Path(img_path).name,
                "label": lp_path.name,
            })

    return {
        "total_images": len(image_files),
        "matched_images": len(label_map),
        "labels_copied": len(details),
        "output_dir": str(out_dir),
        "details": details,
    }


@app.post("/api/integrity/check")
async def api_integrity_check(
    image_dir: str = Form(...),
    label_dir: str = Form(...),
    label_extensions: str = Form("txt,xml,json"),
):
    img_dir = Path(image_dir)
    lbl_dir = Path(label_dir)

    if not img_dir.is_dir():
        return {"error": "图片文件夹不存在"}
    if not lbl_dir.is_dir():
        return {"error": "标签文件夹不存在"}

    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    lbl_exts = {f".{e.strip()}" for e in label_extensions.split(",") if e.strip()}

    image_files = sorted([
        f for f in img_dir.iterdir()
        if f.suffix.lower() in img_exts
    ])
    label_files = sorted([
        f for f in lbl_dir.iterdir()
        if f.suffix.lower() in lbl_exts
    ])

    image_stems = {f.stem: f.name for f in image_files}
    label_stems = {f.stem: f.name for f in label_files}

    images_without_labels = sorted([
        name for stem, name in image_stems.items()
        if stem not in label_stems
    ])
    labels_without_images = sorted([
        name for stem, name in label_stems.items()
        if stem not in image_stems
    ])
    matched_pairs = sorted([
        {"image": image_stems[stem], "label": label_stems[stem]}
        for stem in image_stems.keys() & label_stems.keys()
    ], key=lambda x: x["image"])

    return {
        "total_images": len(image_files),
        "total_labels": len(label_files),
        "matched": len(matched_pairs),
        "images_without_labels": images_without_labels,
        "labels_without_images": labels_without_images,
        "matched_pairs": matched_pairs,
    }


@app.post("/api/stats")
async def api_dataset_stats(
    label_dir: str = Form(...),
    label_format: str = Form("txt"),
    image_dir: str = Form(None),
):
    if not Path(label_dir).is_dir():
        return {"error": "标签文件夹不存在"}

    result = compute_stats(label_dir, label_format, image_dir or None)
    return result


@app.post("/api/rename/preview")
async def api_rename_preview(
    image_dir: str = Form(...),
    prefix: str = Form(""),
    zfill: int = Form(0),
    output_dir: str = Form(""),
):
    plan = preview_rename(image_dir, prefix, zfill, output_dir)
    return {"total": len(plan), "results": plan}


@app.post("/api/rename/execute")
async def api_rename_execute(
    image_dir: str = Form(...),
    prefix: str = Form(""),
    zfill: int = Form(0),
    output_dir: str = Form(""),
):
    plan = execute_rename(image_dir, prefix, zfill, output_dir)
    return {"total": len(plan), "results": plan}
