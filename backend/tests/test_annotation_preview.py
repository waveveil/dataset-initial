import io

import pytest
from PIL import Image

from backend.app.annotation_preview import (
    PreviewImageNotFound,
    PreviewRenderError,
    PreviewSessionNotFound,
    PreviewSessionStore,
    PreviewValidationError,
    parse_class_mapping,
)


def write_image(path, color=(16, 24, 40), size=(100, 80)):
    Image.new("RGB", size, color).save(path)


def create_store_with_dirs(tmp_path):
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    image_dir.mkdir()
    label_dir.mkdir()
    return PreviewSessionStore(), image_dir, label_dir


def test_parse_class_mapping_supports_names_and_full_width_colon():
    assert parse_class_mapping("0: 灭火器\n1：fire truck\n\n") == {
        0: "灭火器",
        1: "fire truck",
    }


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ("0 cat", "缺少冒号"),
        (":cat", "缺少类别 ID"),
        ("0:", "缺少类别名称"),
        ("cat:猫", "ID 必须是整数"),
        ("-1:猫", "不能是负数"),
        ("0:猫\n0:狗", "类别 ID 0 重复"),
    ],
)
def test_parse_class_mapping_rejects_invalid_rows(mapping, message):
    with pytest.raises(PreviewValidationError, match=message):
        parse_class_mapping(mapping)


def test_load_lists_current_directory_in_stable_order_and_keeps_missing_labels(tmp_path):
    store, image_dir, label_dir = create_store_with_dirs(tmp_path)
    nested_dir = image_dir / "nested"
    nested_dir.mkdir()

    write_image(image_dir / "b.PNG")
    write_image(image_dir / "A.jpg")
    write_image(nested_dir / "ignored.jpg")
    (image_dir / "notes.txt").write_text("not an image", encoding="utf-8")
    (label_dir / "A.txt").write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")

    payload = store.create(str(image_dir), str(label_dir))

    assert payload["total"] == 2
    assert payload["missing_labels"] == 1
    assert [item["name"] for item in payload["images"]] == ["A.jpg", "b.PNG"]
    assert [item["has_label"] for item in payload["images"]] == [True, False]
    assert all(item["id"] and "path" not in item for item in payload["images"])


def test_load_validates_directories_and_empty_image_directory(tmp_path):
    store = PreviewSessionStore()
    labels = tmp_path / "labels"
    labels.mkdir()

    with pytest.raises(PreviewValidationError, match="图片文件夹不存在"):
        store.create(str(tmp_path / "missing"), str(labels))

    images = tmp_path / "images"
    images.mkdir()
    with pytest.raises(PreviewValidationError, match="没有支持的图片文件"):
        store.create(str(images), str(labels))


def test_render_draws_valid_boxes_and_reports_skipped_rows(tmp_path):
    store, image_dir, label_dir = create_store_with_dirs(tmp_path)
    write_image(image_dir / "frame.jpg")
    (label_dir / "frame.txt").write_text(
        "0 0.5 0.5 0.4 0.5\n"
        "1 0.05 0.05 0.4 0.4\n"
        "bad row\n"
        "2 nan 0.5 0.2 0.2\n"
        "3 0.5 0.5 -0.2 0.2\n"
        "4 2 2 0.2 0.2\n"
        "-1 0.5 0.5 0.2 0.2\n",
        encoding="utf-8",
    )
    loaded = store.create(str(image_dir), str(label_dir))
    image_record = store.get_image(loaded["session_id"], loaded["images"][0]["id"])

    from backend.app.annotation_preview import _render_image

    rendered = _render_image(image_record, {0: "火焰", 1: "edge box"})

    assert rendered.label_found is True
    assert rendered.box_count == 2
    assert rendered.skipped_count == 5
    image = Image.open(io.BytesIO(rendered.content))
    assert image.size == (100, 80)
    assert image.getpixel((30, 20)) != (16, 24, 40)


def test_render_missing_label_returns_original_image_with_metadata(tmp_path):
    store, image_dir, label_dir = create_store_with_dirs(tmp_path)
    write_image(image_dir / "plain.png", color=(11, 22, 33))
    loaded = store.create(str(image_dir), str(label_dir))
    image_record = store.get_image(loaded["session_id"], loaded["images"][0]["id"])

    from backend.app.annotation_preview import _render_image

    rendered = _render_image(image_record, {})

    assert rendered.label_found is False
    assert rendered.box_count == 0
    assert rendered.skipped_count == 0
    image = Image.open(io.BytesIO(rendered.content))
    assert image.getpixel((50, 40)) == (11, 22, 33)


def test_store_rejects_unknown_session_and_unknown_image(tmp_path):
    store, image_dir, label_dir = create_store_with_dirs(tmp_path)
    write_image(image_dir / "frame.jpg")
    loaded = store.create(str(image_dir), str(label_dir))

    with pytest.raises(PreviewSessionNotFound, match="不存在或已过期"):
        store.get_image("not-a-session", loaded["images"][0]["id"])

    with pytest.raises(PreviewImageNotFound, match="不属于当前预览会话"):
        store.get_image(loaded["session_id"], "../outside.jpg")


def test_render_reports_corrupt_image(tmp_path):
    store, image_dir, label_dir = create_store_with_dirs(tmp_path)
    (image_dir / "broken.jpg").write_bytes(b"not an image")
    loaded = store.create(str(image_dir), str(label_dir))
    image_record = store.get_image(loaded["session_id"], loaded["images"][0]["id"])

    from backend.app.annotation_preview import _render_image

    with pytest.raises(PreviewRenderError, match="无法读取图片"):
        _render_image(image_record, {})


def test_preview_store_expires_sessions(monkeypatch, tmp_path):
    store, image_dir, label_dir = create_store_with_dirs(tmp_path)
    store.ttl_seconds = 10
    write_image(image_dir / "frame.jpg")

    monotonic_values = iter([0.0, 11.0])
    monkeypatch.setattr("backend.app.annotation_preview.time.monotonic", lambda: next(monotonic_values))
    loaded = store.create(str(image_dir), str(label_dir))

    with pytest.raises(PreviewSessionNotFound, match="不存在或已过期"):
        store.get_image(loaded["session_id"], loaded["images"][0]["id"])
