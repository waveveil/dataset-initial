import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import UPLOAD_DIR, OUTPUT_DIR
from .scene_filter import filter_by_scene
from .dedup import dedup_and_sample
from .rename import preview_rename, execute_rename


class ExportRequest(BaseModel):
    file_paths: list[str]
    output_dir: str
    label_dirs: list[str] | None = None

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
        from fastapi.responses import Response
        return Response(status_code=404)
    return FileResponse(file_path)


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
    label_dirs: str = Form(None),
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

    parsed_label_dirs = None
    if label_dirs:
        parsed_label_dirs = [d.strip() for d in label_dirs.split(",") if d.strip()]

    results = dedup_and_sample(
        str(work_dir),
        target_count=target_count,
        phash_threshold=phash_threshold,
        label_dirs=parsed_label_dirs,
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
