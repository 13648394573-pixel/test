from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path, PurePosixPath
import re
import textwrap
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

from app.local_runner.contracts import ArtifactPayload


class UnsafeArtifactPathError(Exception):
    pass


_SECRET_PATTERN = re.compile(
    r"(?i)((?:password|passwd|pwd|token|secret|loid|pppoe[-_ ]?(?:user|pass))\s*[:=]\s*)([^\s]+)"
)


class GeneratedEvidenceWriter:
    def __init__(
        self,
        root: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(UTC))

    def write_text_and_png(
        self,
        relative_base: str,
        *,
        title: str,
        text: str,
        redaction_values: tuple[str, ...] = (),
    ) -> tuple[ArtifactPayload, ArtifactPayload]:
        base = self._safe_relative(relative_base)
        redacted_text = self._redact(text, redaction_values)
        timestamp = self.clock().astimezone(UTC).isoformat()
        rendered = f"{title}\nCaptured: {timestamp}\n\n{redacted_text}\n"
        text_path = self._absolute(PurePosixPath(f"{base}.txt"))
        png_path = self._absolute(PurePosixPath(f"{base}.png"))
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_bytes = rendered.encode("utf-8")
        text_path.write_bytes(text_bytes)
        self._render_png(png_path, rendered)
        png_bytes = png_path.read_bytes()
        return (
            self._payload(text_path, "text/plain", text_bytes, True),
            self._payload(png_path, "image/png", png_bytes, True),
        )

    def register_screenshot(
        self, relative_path: str, content: bytes
    ) -> ArtifactPayload:
        relative = self._safe_relative(relative_path)
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Screenshot must be PNG data")
        path = self._absolute(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return self._payload(path, "image/png", content, False)

    def _redact(self, value: str, explicit_values: tuple[str, ...]) -> str:
        redacted = value
        for secret in sorted((item for item in explicit_values if item), key=len, reverse=True):
            redacted = redacted.replace(secret, "[REDACTED]")
        return _SECRET_PATTERN.sub(r"\1[REDACTED]", redacted)

    def _render_png(self, path: Path, rendered: str) -> None:
        font = self._load_font()
        lines: list[str] = []
        for line in rendered.expandtabs(4).splitlines() or [""]:
            lines.extend(textwrap.wrap(line, width=180, replace_whitespace=False) or [""])
        probe = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(probe)
        widths = [draw.textlength(line, font=font) for line in lines]
        width = min(1920, max(640, int(max(widths, default=0)) + 48))
        line_height = 18
        height = max(160, 40 + line_height * len(lines))
        image = Image.new("RGB", (width, height), color=(22, 27, 34))
        draw = ImageDraw.Draw(image)
        y = 20
        for line in lines:
            draw.text((24, y), line, font=font, fill=(230, 237, 243))
            y += line_height
        image.save(path, format="PNG", optimize=True)

    @staticmethod
    def _load_font():
        for candidate in (
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/consola.ttf"),
        ):
            if candidate.is_file():
                return ImageFont.truetype(str(candidate), 16)
        return ImageFont.load_default()

    def _safe_relative(self, value: str) -> PurePosixPath:
        normalized = value.replace("\\", "/")
        relative = PurePosixPath(normalized)
        if (
            not normalized
            or relative.is_absolute()
            or ".." in relative.parts
            or any(":" in part for part in relative.parts)
        ):
            raise UnsafeArtifactPathError(value)
        return relative

    def _absolute(self, relative: PurePosixPath) -> Path:
        path = (self.root / Path(*relative.parts)).resolve()
        if self.root != path and self.root not in path.parents:
            raise UnsafeArtifactPathError(str(relative))
        return path

    def _payload(
        self, path: Path, media_type: str, content: bytes, redacted: bool
    ) -> ArtifactPayload:
        return ArtifactPayload(
            original_name=path.name,
            media_type=media_type,
            storage_path=path.relative_to(self.root).as_posix(),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            redacted=redacted,
        )
