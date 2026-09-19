from pathlib import Path

import pytest
from PIL import Image

from app.local_runner.evidence import GeneratedEvidenceWriter, UnsafeArtifactPathError
from app.local_runner.contracts import ArtifactPayload


def test_generated_evidence_is_redacted_hashed_and_rendered(tmp_path) -> None:
    writer = GeneratedEvidenceWriter(tmp_path)
    artifacts = writer.write_text_and_png(
        "runs/run-1/session-1/ipoe",
        title="IPoE WAN information",
        text="Address: 198.51.100.7\nPassword: visible-value\nToken=abc123",
        redaction_values=("198.51.100.7",),
    )

    assert len(artifacts) == 2
    text_artifact = next(item for item in artifacts if item.media_type == "text/plain")
    png_artifact = next(item for item in artifacts if item.media_type == "image/png")
    written_text = (tmp_path / text_artifact.storage_path).read_text(encoding="utf-8")
    assert "198.51.100.7" not in written_text
    assert "visible-value" not in written_text
    assert "abc123" not in written_text
    assert "[REDACTED]" in written_text
    assert len(text_artifact.sha256) == 64
    assert len(png_artifact.sha256) == 64
    with Image.open(tmp_path / png_artifact.storage_path) as image:
        assert image.format == "PNG"
        assert image.width <= 1920


@pytest.mark.parametrize("path", ["../outside", "runs/../../outside", "C:/outside"])
def test_generated_evidence_rejects_absolute_or_traversal_paths(tmp_path, path) -> None:
    with pytest.raises(UnsafeArtifactPathError):
        GeneratedEvidenceWriter(tmp_path).write_text_and_png(
            path, title="Unsafe", text="data"
        )


def test_register_screenshot_writes_only_below_root(tmp_path) -> None:
    writer = GeneratedEvidenceWriter(tmp_path)
    payload = writer.register_screenshot(
        "runs/run-1/session-1/onu.png", b"\x89PNG\r\n\x1a\nexample"
    )
    assert payload.storage_path == "runs/run-1/session-1/onu.png"
    assert (tmp_path / payload.storage_path).is_file()


def test_register_artifact_preserves_redaction_and_requires_content(tmp_path) -> None:
    writer = GeneratedEvidenceWriter(tmp_path)
    payload = writer.register_artifact(
        "onu/status.txt",
        ArtifactPayload(
            "status.txt",
            "text/plain",
            content=b"redacted status",
            redacted=True,
        ),
    )

    assert payload.storage_path == "onu/status.txt"
    assert payload.redacted is True
    assert payload.sha256
    with pytest.raises(ValueError, match="content"):
        writer.register_artifact(
            "onu/empty.txt", ArtifactPayload("empty.txt", "text/plain")
        )
