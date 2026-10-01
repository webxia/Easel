"""Attempt-scoped persistence for Material Layer contracts and locators."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import posixpath
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from easel.materials.domain import MaterialAsset, MaterialBundle, MaterialPlan, SupplyRun

_ModelT = TypeVar("_ModelT", bound=BaseModel)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class AttemptMaterialStoreError(ValueError):
    """Raised when an Attempt material path or record is unsafe or invalid."""


class GenerationRecordNotFound(AttemptMaterialStoreError):
    """Raised only when an Attempt has no record for a generation request id."""


class AttemptMaterialStore:
    """Read and write material records only beneath one Attempt's materials/."""

    _HYPIT_MEDIA_EXTENSIONS = {
        "video": frozenset({".m4v", ".mov", ".mp4", ".webm"}),
        "image": frozenset({".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}),
        "audio": frozenset({".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".opus", ".wav"}),
    }

    def __init__(self, attempt_root: str | Path):
        provided_root = Path(attempt_root).expanduser()
        if provided_root.is_symlink():
            raise AttemptMaterialStoreError("Attempt root must not be a symlink")
        try:
            root = provided_root.resolve(strict=True)
        except OSError as exc:
            raise AttemptMaterialStoreError("Attempt root must exist") from exc
        if not root.is_dir():
            raise AttemptMaterialStoreError("Attempt root must be a directory")
        self.attempt_root = root
        self.materials_root = root / "materials"
        self._reject_symlink_components(self.materials_root)
        self.materials_root.mkdir(parents=False, exist_ok=True)
        self._verify_material_path(self.materials_root)
        for directory in ("assets", "supply-runs", "generation-runs"):
            child = self.materials_root / directory
            self._reject_symlink_components(child)
            child.mkdir(exist_ok=True)
            self._verify_material_path(child)

    def write_plan(self, plan: MaterialPlan) -> str:
        return self._write_model("materials/plan.json", plan)

    def write_observation_record(self, record_id: str, record: dict) -> str:
        """Atomically retain a visual input, report or nominated candidate batch."""
        self._validate_id(record_id)
        locator = f"materials/observations/{record_id}.json"
        self._write_json(locator, record)
        return locator

    def read_recovery_record(self, request_id: str) -> dict | None:
        self._validate_id(request_id)
        path = self._path(f"materials/recoveries/{request_id}.json")
        self._reject_symlink_components(path)
        self._verify_material_path(path)
        if not path.exists():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptMaterialStoreError("素材恢复记录无效") from exc
        if not isinstance(record, dict):
            raise AttemptMaterialStoreError("素材恢复记录必须是对象")
        return record

    def write_recovery_record(self, request_id: str, record: dict) -> None:
        self._validate_id(request_id)
        self._write_json(f"materials/recoveries/{request_id}.json", record)

    def read_plan(self) -> MaterialPlan:
        return self._read_model("materials/plan.json", MaterialPlan)

    def write_bundle(self, bundle: MaterialBundle) -> str:
        return self._write_model("materials/bundle.json", bundle)

    def read_bundle(self) -> MaterialBundle:
        return self._read_model("materials/bundle.json", MaterialBundle)

    def write_asset(self, asset: MaterialAsset) -> str:
        locator = self._canonical_locator(asset.file.path)
        prefix = f"materials/assets/{asset.asset_id}/"
        if not locator.startswith(prefix):
            raise AttemptMaterialStoreError("MaterialAsset.file.path must be inside its asset directory")
        directory = self._path(f"materials/assets/{asset.asset_id}")
        self._reject_symlink_components(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self._verify_material_path(directory)
        record_locator = f"materials/assets/{asset.asset_id}/asset.json"
        self._write_model(record_locator, asset)
        self._write_json(
            f"materials/assets/{asset.asset_id}/source.json",
            {
                "source": asset.source.model_dump(mode="json"),
                "rights": asset.rights.model_dump(mode="json"),
            },
        )
        self._write_json(
            f"materials/assets/{asset.asset_id}/analysis.json",
            {
                "technical": asset.technical.model_dump(mode="json"),
                "semantic": asset.semantic.model_dump(mode="json"),
            },
        )
        return locator

    def write_asset_bytes(self, asset_id: str, filename: str, data: bytes) -> str:
        """Atomically stage acquired bytes beneath one asset directory."""
        asset_id = self._validate_id(asset_id)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", filename) or filename in {".", ".."}:
            raise AttemptMaterialStoreError("Material asset filename is invalid")
        directory = self._path(f"materials/assets/{asset_id}")
        self._reject_symlink_components(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self._verify_material_path(directory)
        locator = f"materials/assets/{asset_id}/{filename}"
        target = self._path(locator)
        self._reject_symlink_components(target)
        if target.exists():
            raise AttemptMaterialStoreError("Material asset bytes already exist")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".asset-", suffix=".tmp", dir=directory)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            self._reject_symlink_components(target)
            self._verify_material_path(directory)
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        return locator

    def write_acquisition_evidence(self, asset_id: str, payload: dict[str, object]) -> str:
        """Persist sanitized acquisition facts as an Attempt-local sidecar."""
        asset_id = self._validate_id(asset_id)
        return self._write_json(f"materials/assets/{asset_id}/acquisition.json", payload)

    def read_acquisition_evidence(self, asset_id: str) -> dict[str, object]:
        """Read an existing acquisition sidecar without following workspace symlinks."""
        asset_id = self._validate_id(asset_id)
        locator = f"materials/assets/{asset_id}/acquisition.json"
        path = self._path(locator)
        self._reject_symlink_components(path)
        self._verify_material_path(path)
        if not path.exists():
            return {}
        if not path.is_file():
            raise AttemptMaterialStoreError("Acquisition evidence must be a regular file")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptMaterialStoreError("Invalid acquisition evidence") from exc
        if not isinstance(payload, dict):
            raise AttemptMaterialStoreError("Acquisition evidence must be a JSON object")
        return payload

    def discard_uncommitted_asset(self, asset_id: str) -> None:
        """Remove an incomplete asset directory created by a failed acquisition."""
        asset_id = self._validate_id(asset_id)
        directory = self._path(f"materials/assets/{asset_id}")
        self._reject_symlink_components(directory)
        self._verify_material_path(directory)
        if directory.exists():
            shutil.rmtree(directory)

    def read_asset(self, asset_id: str) -> MaterialAsset:
        return self._read_model(f"materials/assets/{self._validate_id(asset_id)}/asset.json", MaterialAsset)

    def write_supply_run(self, run: SupplyRun) -> str:
        directory = self._path(f"materials/supply-runs/{self._validate_id(run.supply_run_id)}")
        self._reject_symlink_components(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self._verify_material_path(directory)
        return self._write_model(
            f"materials/supply-runs/{run.supply_run_id}/result.json", run
        )

    def read_supply_run(self, supply_run_id: str) -> SupplyRun:
        run_id = self._validate_id(supply_run_id)
        return self._read_model(f"materials/supply-runs/{run_id}/result.json", SupplyRun)

    def write_generation_record(self, generation_id: str, payload: dict[str, object]) -> str:
        """Persist provider-neutral execution facts under the owning Attempt."""
        run_id = self._validate_id(generation_id)
        return self._write_json(f"materials/generation-runs/{run_id}/result.json", payload)

    @contextmanager
    def generation_lock(self, generation_id: str):
        """Hold a request across submission and local intake; never steal a live lock."""
        run_id = self._validate_id(generation_id)
        path = self._path(f"materials/generation-runs/{run_id}/execution.lock")
        self._reject_symlink_components(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._verify_material_path(path.parent)
        with path.open('a+b') as stream:
            try:
                if os.name == 'nt':
                    import msvcrt
                    if stream.tell() == 0:
                        stream.write(b'0')
                        stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise AttemptMaterialStoreError('该素材请求仍在执行，不能并发提交或接管') from exc
            try:
                yield
            finally:
                if os.name == 'nt':
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def read_generation_record(self, generation_id: str) -> dict[str, object]:
        run_id = self._validate_id(generation_id)
        locator = f"materials/generation-runs/{run_id}/result.json"
        path = self._path(locator)
        self._reject_symlink_components(path)
        self._verify_material_path(path)
        if not path.is_file():
            raise GenerationRecordNotFound(f"Generation record not found: {run_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AttemptMaterialStoreError("Invalid generation record") from exc
        if not isinstance(payload, dict):
            raise AttemptMaterialStoreError("Generation record must be a JSON object")
        return payload

    def list_generation_records(self) -> tuple[dict[str, object], ...]:
        """Read generation records without following paths outside this Attempt."""
        root = self._path("materials/generation-runs")
        self._reject_symlink_components(root)
        self._verify_material_path(root)
        records: list[dict[str, object]] = []
        for directory in sorted(root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir():
                continue
            generation_id = self._validate_id(directory.name)
            try:
                records.append(self.read_generation_record(generation_id))
            except GenerationRecordNotFound:
                continue
        return tuple(records)

    def resolve_asset_locator(self, locator: str) -> Path:
        """Resolve an existing canonical workspace locator to a regular file."""
        canonical = self._canonical_locator(locator)
        if not canonical.startswith("materials/assets/"):
            raise AttemptMaterialStoreError("Asset locator must be beneath materials/assets/")
        path = self._path(canonical)
        self._reject_symlink_components(path)
        self._verify_material_path(path)
        if not path.is_file():
            raise AttemptMaterialStoreError("Asset locator must resolve to an existing file")
        return path

    def hypit_source_path(self, asset: MaterialAsset, authoring_source: str) -> str:
        """Return a relative media src from a workspace-local Hypit authoring file.

        ``authoring_source`` is a canonical workspace locator, which may name a
        not-yet-authored file. The method only resolves the persisted asset
        beneath materials/ and does not read or validate files outside it.
        """
        media_locator = self._canonical_locator(asset.file.path)
        media_path = self.resolve_asset_locator(media_locator)
        supported_extensions = self._HYPIT_MEDIA_EXTENSIONS[asset.media_type.value]
        if media_path.suffix.lower() not in supported_extensions:
            raise AttemptMaterialStoreError(
                f"Asset extension is not supported by Hypit media:{asset.media_type.value}"
            )
        source_locator = self._canonical_workspace_path(authoring_source)
        relative = posixpath.relpath(media_locator, PurePosixPath(source_locator).parent.as_posix())
        if PurePosixPath(relative).is_absolute():
            raise AttemptMaterialStoreError("Hypit media src must be relative to its authoring source")
        return relative

    def _write_model(self, locator: str, model: BaseModel) -> str:
        self._write_json(locator, model.model_dump(mode="json"))
        return self._canonical_locator(locator)

    def _read_model(self, locator: str, model_type: type[_ModelT]) -> _ModelT:
        path = self._path(locator)
        self._reject_symlink_components(path)
        self._verify_material_path(path)
        if not path.is_file():
            raise AttemptMaterialStoreError(f"Material record not found: {locator}")
        try:
            return model_type.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            raise AttemptMaterialStoreError(f"Invalid Material record: {locator}") from exc

    def _write_json(self, locator: str, payload: dict[str, object]) -> None:
        canonical = self._canonical_locator(locator)
        target = self._path(canonical)
        self._reject_symlink_components(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._verify_material_path(target.parent)
        if target.exists() and not target.is_file():
            raise AttemptMaterialStoreError("Material record target must be a regular file")
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(prefix=".material-", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            self._reject_symlink_components(target)
            self._verify_material_path(target.parent)
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _path(self, locator: str) -> Path:
        canonical = self._canonical_workspace_path(locator)
        return self.attempt_root.joinpath(*PurePosixPath(canonical).parts)

    @classmethod
    def _canonical_locator(cls, locator: str) -> str:
        canonical = cls._canonical_workspace_path(locator)
        if not canonical.startswith("materials/") or canonical == "materials/":
            raise AttemptMaterialStoreError("Material locator must be beneath materials/")
        return canonical

    @staticmethod
    def _canonical_workspace_path(locator: str) -> str:
        if not isinstance(locator, str) or not locator or "\\" in locator:
            raise AttemptMaterialStoreError("Locator must be a non-empty POSIX relative path")
        path = PurePosixPath(locator)
        if path.is_absolute() or locator.startswith("~") or any(part in ("", ".", "..") for part in locator.split("/")):
            raise AttemptMaterialStoreError("Locator must be canonical and workspace-relative")
        canonical = path.as_posix()
        if canonical != locator:
            raise AttemptMaterialStoreError("Locator must be canonical and workspace-relative")
        return canonical

    @staticmethod
    def _validate_id(value: str) -> str:
        if not isinstance(value, str) or not _ID_RE.fullmatch(value) or value in {".", ".."}:
            raise AttemptMaterialStoreError("Material record ID is invalid")
        return value

    def _reject_symlink_components(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.attempt_root)
        except ValueError as exc:
            raise AttemptMaterialStoreError("Path escapes Attempt workspace") from exc
        current = self.attempt_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise AttemptMaterialStoreError("Symlinks are not allowed in Material workspace paths")

    def _verify_material_path(self, path: Path) -> None:
        self._verify_workspace_path(path)
        try:
            path.resolve(strict=False).relative_to(self.materials_root)
        except ValueError as exc:
            raise AttemptMaterialStoreError("Material path escapes materials/") from exc

    def _verify_workspace_path(self, path: Path) -> None:
        self._reject_symlink_components(path)
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(self.attempt_root)
        except ValueError as exc:
            raise AttemptMaterialStoreError("Path escapes Attempt workspace") from exc
