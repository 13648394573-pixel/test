from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


class ArtifactMissingError(Exception):
    pass


class ArtifactIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class StoredArtifact:
    storage_path: str
    file_size: int
    sha256: str


class ReportStorage:
    def __init__(self, root: str | Path, evidence_root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.evidence_root = Path(evidence_root).expanduser().resolve()

    def resolve(self, storage_path: str) -> Path:
        return self._resolve_within(self.root, storage_path)

    def write_html(self, report_id: str, content: str) -> StoredArtifact:
        relative = f"reports/{report_id}/report.html"
        destination = self.resolve(relative)
        return self._atomic_write(destination, content.encode("utf-8"))

    def open_verified(self, storage_path: str, expected_sha256: str) -> Path:
        path = self.resolve(storage_path)
        if not path.is_file():
            raise ArtifactMissingError(storage_path)
        if self._hash(path) != expected_sha256:
            raise ArtifactIntegrityError(storage_path)
        return path

    def create_archive(
        self,
        archive_id: str,
        report_storage_path: str,
        report_sha256: str,
        evidences: list[dict],
        manifest: dict,
    ) -> StoredArtifact:
        report_path = self.open_verified(report_storage_path, report_sha256)
        evidence_paths = []
        for item in evidences:
            path = self._resolve_within(
                self.evidence_root,
                item["storage_path"],
            )
            if not path.is_file():
                raise ArtifactMissingError(item["storage_path"])
            if self._hash(path) != item["sha256"]:
                raise ArtifactIntegrityError(item["storage_path"])
            evidence_paths.append((item, path))

        relative = f"archives/{archive_id}.zip"
        destination = self.resolve(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            with ZipFile(temporary, "x", compression=ZIP_DEFLATED) as package:
                package.write(report_path, "report.html")
                package.writestr(
                    "manifest.json",
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    ),
                )
                for item, path in evidence_paths:
                    # Align zip entry with the database evidences.storage_path
                    # so archived files can be traced back to the evidence
                    # store without a second mapping layer.
                    package.write(
                        path,
                        f"evidence/{item['storage_path']}",
                    )
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        return self._metadata(destination)

    def delete(self, storage_path: str) -> None:
        self.resolve(storage_path).unlink(missing_ok=True)

    def _atomic_write(self, destination: Path, content: bytes) -> StoredArtifact:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise
        return self._metadata(destination)

    @staticmethod
    def _resolve_within(root: Path, storage_path: str) -> Path:
        candidate = (root / storage_path).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("Artifact path is outside configured root")
        return candidate

    @staticmethod
    def _hash(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def _metadata(self, path: Path) -> StoredArtifact:
        return StoredArtifact(
            storage_path=path.relative_to(self.root).as_posix(),
            file_size=path.stat().st_size,
            sha256=self._hash(path),
        )
