from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


class EvidenceFileTooLargeError(Exception):
    pass


class EvidenceFileMissingError(Exception):
    pass


@dataclass(frozen=True)
class StoredEvidence:
    storage_path: str
    file_size: int
    sha256: str


class EvidenceStorage:
    def __init__(
        self,
        root: str | Path,
        *,
        max_bytes: int,
        chunk_size: int = 64 * 1024,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_bytes = max_bytes
        self.chunk_size = chunk_size

    def store(
        self,
        owner_kind: str,
        owner_id: str,
        original_name: str,
        stream: BinaryIO,
    ) -> StoredEvidence:
        extension = Path(Path(original_name).name).suffix.lower()
        if len(extension) > 20 or not all(
            character.isalnum() or character == "." for character in extension
        ):
            extension = ""
        owner_directory = self.resolve(f"{owner_kind}/{owner_id}")
        owner_directory.mkdir(parents=True, exist_ok=True)
        token = str(uuid4())
        final_path = owner_directory / f"{token}{extension}"
        temporary_path = owner_directory / f".{token}.tmp"
        digest = sha256()
        size = 0
        try:
            with temporary_path.open("xb") as destination:
                while chunk := stream.read(self.chunk_size):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise EvidenceFileTooLargeError(self.max_bytes)
                    digest.update(chunk)
                    destination.write(chunk)
            temporary_path.replace(final_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise
        return StoredEvidence(
            storage_path=final_path.relative_to(self.root).as_posix(),
            file_size=size,
            sha256=digest.hexdigest(),
        )

    def resolve(self, storage_path: str) -> Path:
        candidate = (self.root / storage_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Evidence path is outside evidence root")
        return candidate

    def open_path(self, storage_path: str) -> Path:
        path = self.resolve(storage_path)
        if not path.is_file():
            raise EvidenceFileMissingError(storage_path)
        return path

    def delete(self, storage_path: str) -> None:
        self.resolve(storage_path).unlink(missing_ok=True)
