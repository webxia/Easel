"""Persistent, scoped catalog for registered Attempt ``MaterialAsset`` records.

The catalog is a persistence boundary around the existing MaterialAsset
contract.  It does not define a second asset domain: the record stores one
MaterialAsset plus the library scope, lifecycle timestamps, and the catalog's
physical object locator.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from easel.materials.domain import (
    IntelligenceStatus,
    MaterialAsset,
    MediaType,
    RightsStatus,
    SemanticInference,
    TechnicalStatus,
)
from easel.materials.store import AttemptMaterialStore, AttemptMaterialStoreError


_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MaterialLibraryError(ValueError):
    """Raised when a library record or object cannot be safely persisted."""


class PromotionRejected(MaterialLibraryError):
    """Raised when consent or catalog promotion eligibility is missing."""


class LibraryScope(BaseModel):
    """Opaque tenancy and creator boundary for catalog visibility."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tenant_id: str = Field(min_length=1)
    creator_id: str = Field(min_length=1)

    @field_validator("tenant_id", "creator_id")
    @classmethod
    def valid_token(cls, value: str) -> str:
        if not _TOKEN_RE.fullmatch(value):
            raise ValueError("library scope values contain unsupported characters")
        return value

    @property
    def key(self) -> str:
        return f"{self.tenant_id}:{self.creator_id}"


class PromotionConsent(BaseModel):
    """Explicit, attributable authorization for one catalog promotion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    authorized: bool
    actor_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    consented_at: datetime

    @field_validator("actor_id", "purpose")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("consent fields must not be blank")
        return value.strip()

    @field_validator("consented_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("consented_at must include a timezone")
        return value


class MaterialLibraryUsage(BaseModel):
    """Evidence that a catalog asset was explicitly selected in one Attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    usage_id: str = Field(min_length=1)
    library_asset_id: str = Field(min_length=1)
    source_attempt_id: str = Field(min_length=1)
    creation_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    need_ids: tuple[str, ...] = ()
    usage_kind: str = Field(default="PRODUCTION_SELECTED", min_length=1)
    evidence_ref: str | None = None
    used_at: datetime

    @field_validator("usage_id", "library_asset_id", "source_attempt_id", "creation_id", "attempt_id", "usage_kind")
    @classmethod
    def valid_usage_token(cls, value: str) -> str:
        if not _TOKEN_RE.fullmatch(value):
            raise ValueError("usage value contains unsupported characters")
        return value

    @field_validator("need_ids")
    @classmethod
    def unique_need_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not _TOKEN_RE.fullmatch(value) for value in values) or len(values) != len(set(values)):
            raise ValueError("usage need_ids must be unique valid IDs")
        return tuple(sorted(values))

    @field_validator("used_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("used_at must include a timezone")
        return value


class MaterialLibraryRecord(BaseModel):
    """Catalog envelope; the material itself remains the V1.3 MaterialAsset."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    library_asset_id: str = Field(min_length=1)
    scope: LibraryScope
    asset: MaterialAsset
    physical_locator: str = Field(min_length=1)
    source_creation_id: str | None = None
    source_attempt_id: str = Field(min_length=1)
    provenance: dict[str, Any] = Field(default_factory=dict)
    lifecycle_status: str = Field(default="ACTIVE", min_length=1)
    promotion_consent: PromotionConsent | None = None
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None

    @field_validator("library_asset_id", "source_attempt_id", "lifecycle_status")
    @classmethod
    def valid_record_token(cls, value: str) -> str:
        if not _TOKEN_RE.fullmatch(value):
            raise ValueError("library record value contains unsupported characters")
        return value

    @field_validator("physical_locator")
    @classmethod
    def relative_locator(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or "\\" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or path.as_posix() != value
        ):
            raise ValueError("physical_locator must be a canonical relative path")
        return value

    @model_validator(mode="after")
    def timezone_aware_timestamps(self) -> MaterialLibraryRecord:
        for name in ("created_at", "updated_at", "last_used_at"):
            value = getattr(self, name)
            if value is not None and value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be earlier than created_at")
        if self.last_used_at is not None and self.last_used_at < self.created_at:
            raise ValueError("last_used_at cannot be earlier than created_at")
        if self.library_asset_id != f"lib-{self.asset.file.sha256}":
            raise ValueError("library_asset_id must be the stable content identity")
        return self

    @field_validator("source_creation_id")
    @classmethod
    def valid_source_creation(cls, value: str | None) -> str | None:
        if value is not None and not _TOKEN_RE.fullmatch(value):
            raise ValueError("source_creation_id contains unsupported characters")
        return value


class MaterialLibraryCatalog:
    """SQLite metadata catalog with content-addressed, library-owned objects."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS library_assets (
            library_asset_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            physical_locator TEXT NOT NULL,
            source_creation_id TEXT,
            source_attempt_id TEXT NOT NULL,
            provenance_json TEXT NOT NULL DEFAULT '{}',
            asset_json TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL,
            promotion_consent_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_used_at TEXT,
            PRIMARY KEY (tenant_id, creator_id, library_asset_id),
            UNIQUE (tenant_id, creator_id, sha256)
        );
        CREATE INDEX IF NOT EXISTS idx_library_assets_scope
            ON library_assets (tenant_id, creator_id, updated_at);
        CREATE TABLE IF NOT EXISTS library_asset_usage (
            usage_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            library_asset_id TEXT NOT NULL,
            source_attempt_id TEXT NOT NULL,
            creation_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            need_ids_json TEXT NOT NULL,
            usage_kind TEXT NOT NULL,
            evidence_ref TEXT,
            used_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, creator_id, library_asset_id, creation_id, attempt_id),
            FOREIGN KEY (tenant_id, creator_id, library_asset_id)
                REFERENCES library_assets (tenant_id, creator_id, library_asset_id)
        );
        CREATE INDEX IF NOT EXISTS idx_library_usage_asset
            ON library_asset_usage (tenant_id, creator_id, library_asset_id, used_at);
        CREATE INDEX IF NOT EXISTS idx_library_usage_attempt
            ON library_asset_usage (tenant_id, creator_id, creation_id, attempt_id, used_at);
    """

    def __init__(self, root: str | Path):
        provided = Path(root).expanduser()
        if provided.exists() and provided.is_symlink():
            raise MaterialLibraryError("Library root must not be a symlink")
        provided.mkdir(parents=True, exist_ok=True)
        try:
            self.root = provided.resolve(strict=True)
        except OSError as exc:
            raise MaterialLibraryError("Library root is unavailable") from exc
        if not self.root.is_dir():
            raise MaterialLibraryError("Library root must be a directory")
        self.objects_root = self.root / "objects"
        if self.objects_root.exists() and self.objects_root.is_symlink():
            raise MaterialLibraryError("Library objects directory must not be a symlink")
        self.objects_root.mkdir(exist_ok=True)
        self._verify_inside(self.objects_root)
        self.database_path = self.root / "catalog.db"
        if self.database_path.is_symlink():
            raise MaterialLibraryError("Library database must not be a symlink")
        self._initialize()

    def promote_attempt_asset(
        self,
        asset: MaterialAsset,
        source_store: AttemptMaterialStore,
        *,
        scope: LibraryScope,
        source_attempt_id: str,
        source_creation_id: str | None = None,
        consent: PromotionConsent,
    ) -> MaterialLibraryRecord:
        """Promote an eligible Attempt asset after explicit recorded consent.

        The Attempt locator stays on ``asset.file.path``.  The catalog-owned
        copy is exposed separately through ``physical_locator`` so promotion
        cannot silently rewrite Attempt or Bundle data into a global path.
        """
        self._validate_token(source_attempt_id, "source_attempt_id")
        if source_creation_id is not None:
            self._validate_token(source_creation_id, "source_creation_id")
        if not consent.authorized:
            raise PromotionRejected("Explicit Library promotion consent is required")
        self._validate_eligibility(asset, source_store)
        if 'current_creation_only' in asset.rights.usage_constraints:
            try:
                source_plan = source_store.read_plan()
            except (ValueError, OSError) as exc:
                raise PromotionRejected('作品限定素材缺少当前作品来源证据') from exc
            if (not source_creation_id or source_creation_id != source_plan.creation_id
                    or source_attempt_id != source_plan.attempt_id):
                raise PromotionRejected('作品限定素材不能改变或省略来源作品')
        try:
            persisted = source_store.read_asset(asset.asset_id)
            source_path = source_store.resolve_asset_locator(asset.file.path)
        except (AttemptMaterialStoreError, OSError) as exc:
            raise MaterialLibraryError("Attempt asset is not readable") from exc
        if persisted != asset:
            raise MaterialLibraryError("Attempt asset does not match the persisted record")
        digest = self._digest(source_path)
        if digest != asset.file.sha256:
            raise MaterialLibraryError("Attempt asset content identity does not match its bytes")
        if source_path.stat().st_size != asset.file.size:
            raise MaterialLibraryError("Attempt asset size does not match its bytes")

        library_asset_id = f"lib-{asset.file.sha256}"
        suffix = source_path.suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
            suffix = ".bin"
        physical_locator = f"objects/{asset.file.sha256}{suffix}"
        object_path = self._path(physical_locator)
        self._stage_object(source_path, object_path, asset.file.sha256)

        now = datetime.now(timezone.utc)
        record = MaterialLibraryRecord(
            library_asset_id=library_asset_id,
            scope=scope,
            asset=asset,
            physical_locator=physical_locator,
            source_creation_id=source_creation_id,
            source_attempt_id=source_attempt_id,
            provenance={
                "acquisition": source_store.read_acquisition_evidence(asset.asset_id),
                "generation_lineage": [
                    item for item in source_store.list_generation_records()
                    if item.get("asset_id") == asset.asset_id
                ],
            },
            promotion_consent=consent,
            created_at=now,
            updated_at=now,
        )
        existing = self.get(library_asset_id, scope=scope, missing_ok=True)
        if existing is not None:
            if existing.asset.file.sha256 != asset.file.sha256:
                raise MaterialLibraryError("Library identity collision has different content")
            return existing
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO library_assets (
                        library_asset_id, tenant_id, creator_id, sha256,
                        physical_locator, source_creation_id, source_attempt_id, provenance_json, asset_json,
                        lifecycle_status, promotion_consent_json,
                        created_at, updated_at, last_used_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.library_asset_id,
                        scope.tenant_id,
                        scope.creator_id,
                        asset.file.sha256,
                        record.physical_locator,
                        source_creation_id,
                        source_attempt_id,
                        json.dumps(record.provenance, ensure_ascii=False, sort_keys=True),
                        json.dumps(asset.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                        record.lifecycle_status,
                        consent.model_dump_json(),
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                        None,
                    ),
                )
        except sqlite3.IntegrityError:
            concurrent = self.get(library_asset_id, scope=scope, missing_ok=True)
            if concurrent is not None:
                return concurrent
            raise MaterialLibraryError("Library record could not be registered")
        return record

    def get(
        self,
        library_asset_id: str,
        *,
        scope: LibraryScope,
        missing_ok: bool = False,
    ) -> MaterialLibraryRecord | None:
        self._validate_token(library_asset_id, "library_asset_id")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT library_asset_id, tenant_id, creator_id, physical_locator,
                       source_creation_id, source_attempt_id, provenance_json, asset_json, lifecycle_status,
                       promotion_consent_json,
                       created_at, updated_at, last_used_at
                FROM library_assets
                WHERE tenant_id = ? AND creator_id = ? AND library_asset_id = ?
                """,
                (scope.tenant_id, scope.creator_id, library_asset_id),
            ).fetchone()
        if row is None:
            if missing_ok:
                return None
            raise MaterialLibraryError("Library asset not found in scope")
        return self._record_from_row(row)

    def find_by_content(
        self, sha256: str, *, scope: LibraryScope, missing_ok: bool = False
    ) -> MaterialLibraryRecord | None:
        if not _SHA256_RE.fullmatch(sha256):
            raise MaterialLibraryError("sha256 must be lowercase hexadecimal")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT library_asset_id, tenant_id, creator_id, physical_locator,
                       source_creation_id, source_attempt_id, provenance_json, asset_json, lifecycle_status,
                       promotion_consent_json,
                       created_at, updated_at, last_used_at
                FROM library_assets
                WHERE tenant_id = ? AND creator_id = ? AND sha256 = ?
                """,
                (scope.tenant_id, scope.creator_id, sha256),
            ).fetchone()
        if row is None:
            if missing_ok:
                return None
            raise MaterialLibraryError("Library content is not registered in scope")
        return self._record_from_row(row)

    def list_scope(
        self,
        *,
        scope: LibraryScope,
        media_type: MediaType | None = None,
        rights_status: RightsStatus | None = None,
        technical_status: TechnicalStatus | None = None,
        provider: str | None = None,
        creator: str | None = None,
        tags_all: tuple[str, ...] = (),
        tags_any: tuple[str, ...] = (),
        caption: str | None = None,
        sha256: str | None = None,
        lifecycle_status: str = "ACTIVE",
        limit: int = 100,
    ) -> tuple[MaterialLibraryRecord, ...]:
        """Search exact/structured metadata within one mandatory scope.

        Caption matching is a case-insensitive exact check. It is deterministic
        and intentionally has no fuzzy or
        embedding behavior.
        """
        if limit < 1 or limit > 1000:
            raise MaterialLibraryError("Search limit must be between 1 and 1000")
        if sha256 is not None and not _SHA256_RE.fullmatch(sha256):
            raise MaterialLibraryError("sha256 must be lowercase hexadecimal")
        if lifecycle_status:
            self._validate_token(lifecycle_status, "lifecycle_status")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT library_asset_id, tenant_id, creator_id, physical_locator,
                       source_creation_id, source_attempt_id, provenance_json, asset_json, lifecycle_status,
                       promotion_consent_json,
                       created_at, updated_at, last_used_at
                FROM library_assets
                WHERE tenant_id = ? AND creator_id = ? AND lifecycle_status = ?
                ORDER BY created_at, library_asset_id
                """,
                (scope.tenant_id, scope.creator_id, lifecycle_status),
            ).fetchall()
        records = tuple(self._record_from_row(row) for row in rows)
        if media_type is not None:
            records = tuple(item for item in records if item.asset.media_type is media_type)
        if rights_status is not None:
            records = tuple(item for item in records if item.asset.rights.status is rights_status)
        if technical_status is not None:
            records = tuple(item for item in records if item.asset.technical.status is technical_status)
        if provider is not None:
            records = tuple(item for item in records if item.asset.source.provider == provider)
        if creator is not None:
            records = tuple(item for item in records if item.asset.source.creator == creator)
        if tags_all:
            records = tuple(item for item in records if set(tags_all) <= set(item.asset.semantic.tags))
        if tags_any:
            records = tuple(item for item in records if set(tags_any) & set(item.asset.semantic.tags))
        if caption is not None:
            expected_caption = caption.casefold()
            records = tuple(
                item for item in records
                if item.asset.semantic.caption and expected_caption == item.asset.semantic.caption.casefold()
            )
        if sha256 is not None:
            records = tuple(item for item in records if item.asset.file.sha256 == sha256)
        return records[:limit]

    def metadata_search(
        self,
        *,
        scope: LibraryScope,
        **filters: Any,
    ) -> tuple[MaterialLibraryRecord, ...]:
        """Named search entry point for exact and structured catalog filters."""
        return self.list_scope(scope=scope, **filters)

    def update_semantic_inferences(
        self,
        library_asset_id: str,
        *,
        scope: LibraryScope,
        inferences: tuple[SemanticInference, ...],
        intelligence_status: IntelligenceStatus,
        intelligence_error: str | None = None,
    ) -> MaterialLibraryRecord:
        """Update only the Asset's inference channel, preserving source facts."""
        record = self.get(library_asset_id, scope=scope)
        semantic = record.asset.semantic.model_copy(update={
            "inferences": inferences,
            "intelligence_status": intelligence_status,
            "intelligence_error": intelligence_error,
        })
        updated_asset = record.asset.model_copy(update={"semantic": semantic})
        updated_at = max(datetime.now(timezone.utc), record.created_at)
        updated = record.model_copy(update={"asset": updated_asset, "updated_at": updated_at})
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE library_assets SET asset_json=?, updated_at=?
                WHERE tenant_id=? AND creator_id=? AND library_asset_id=?
                """,
                (
                    json.dumps(updated_asset.model_dump(mode="json"), ensure_ascii=False, sort_keys=True),
                    updated_at.isoformat(),
                    scope.tenant_id,
                    scope.creator_id,
                    library_asset_id,
                ),
            )
        if cursor.rowcount != 1:
            raise MaterialLibraryError("Library semantic record could not be updated")
        return updated

    def record_usage(
        self,
        library_asset_id: str,
        *,
        scope: LibraryScope,
        creation_id: str,
        attempt_id: str,
        need_ids: tuple[str, ...],
        evidence_ref: str | None = None,
        used_at: datetime | None = None,
    ) -> MaterialLibraryUsage:
        """Record a caller-confirmed production selection, idempotently.

        Calling this method is an assertion from the integration boundary that
        the asset was actually selected. Candidate discovery never writes usage.
        """
        for field, value in (("creation_id", creation_id), ("attempt_id", attempt_id)):
            self._validate_token(value, field)
        record = self.get(library_asset_id, scope=scope)
        if record.lifecycle_status != "ACTIVE":
            raise MaterialLibraryError("Inactive Library assets cannot be recorded as used")
        self.resolve_physical_locator(record)
        timestamp = (used_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
        usage_id = "usage-" + hashlib.sha256(
            f"{scope.tenant_id}\0{scope.creator_id}\0{library_asset_id}\0{creation_id}\0{attempt_id}".encode("utf-8")
        ).hexdigest()[:32]
        usage = MaterialLibraryUsage(
            usage_id=usage_id,
            library_asset_id=library_asset_id,
            source_attempt_id=record.source_attempt_id,
            creation_id=creation_id,
            attempt_id=attempt_id,
            need_ids=need_ids,
            evidence_ref=evidence_ref,
            used_at=timestamp,
        )
        with self._connect() as connection:
            existing = connection.execute(
                """
                SELECT usage_id, library_asset_id, source_attempt_id, creation_id,
                       attempt_id, need_ids_json, usage_kind, evidence_ref, used_at
                FROM library_asset_usage WHERE tenant_id=? AND creator_id=?
                  AND library_asset_id=? AND creation_id=? AND attempt_id=?
                """,
                (scope.tenant_id, scope.creator_id, library_asset_id, creation_id, attempt_id),
            ).fetchone()
            if existing is not None:
                prior = self._usage_from_row(existing)
                merged_need_ids = tuple(sorted(set(prior.need_ids) | set(usage.need_ids)))
                if prior.need_ids != merged_need_ids:
                    connection.execute(
                        "UPDATE library_asset_usage SET need_ids_json=? WHERE usage_id=?",
                        (json.dumps(merged_need_ids), prior.usage_id),
                    )
                return prior.model_copy(update={"need_ids": merged_need_ids})
            connection.execute(
                """
                INSERT INTO library_asset_usage (
                    usage_id, tenant_id, creator_id, library_asset_id,
                    source_attempt_id, creation_id, attempt_id, need_ids_json,
                    usage_kind, evidence_ref, used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    usage.usage_id, scope.tenant_id, scope.creator_id,
                    usage.library_asset_id, usage.source_attempt_id,
                    usage.creation_id, usage.attempt_id,
                    json.dumps(usage.need_ids), usage.usage_kind,
                    usage.evidence_ref, usage.used_at.isoformat(),
                ),
            )
            connection.execute(
                "UPDATE library_assets SET last_used_at=?, updated_at=? WHERE tenant_id=? AND creator_id=? AND library_asset_id=?",
                (usage.used_at.isoformat(), usage.used_at.isoformat(), scope.tenant_id, scope.creator_id, library_asset_id),
            )
        return usage

    def usage_for_asset(
        self, library_asset_id: str, *, scope: LibraryScope
    ) -> tuple[MaterialLibraryUsage, ...]:
        self.get(library_asset_id, scope=scope)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT usage_id, library_asset_id, source_attempt_id, creation_id,
                       attempt_id, need_ids_json, usage_kind, evidence_ref, used_at
                FROM library_asset_usage WHERE tenant_id=? AND creator_id=? AND library_asset_id=?
                ORDER BY used_at, creation_id, attempt_id
                """,
                (scope.tenant_id, scope.creator_id, library_asset_id),
            ).fetchall()
        return tuple(self._usage_from_row(row) for row in rows)

    def usage_for_attempt(
        self, creation_id: str, attempt_id: str, *, scope: LibraryScope
    ) -> tuple[MaterialLibraryUsage, ...]:
        self._validate_token(creation_id, "creation_id")
        self._validate_token(attempt_id, "attempt_id")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT usage_id, library_asset_id, source_attempt_id, creation_id,
                       attempt_id, need_ids_json, usage_kind, evidence_ref, used_at
                FROM library_asset_usage WHERE tenant_id=? AND creator_id=? AND creation_id=? AND attempt_id=?
                ORDER BY used_at, library_asset_id
                """,
                (scope.tenant_id, scope.creator_id, creation_id, attempt_id),
            ).fetchall()
        return tuple(self._usage_from_row(row) for row in rows)

    def _usage_from_row(self, row: sqlite3.Row) -> MaterialLibraryUsage:
        try:
            return MaterialLibraryUsage.model_validate_json(json.dumps({
                "usage_id": row["usage_id"],
                "library_asset_id": row["library_asset_id"],
                "source_attempt_id": row["source_attempt_id"],
                "creation_id": row["creation_id"],
                "attempt_id": row["attempt_id"],
                "need_ids": json.loads(row["need_ids_json"]),
                "usage_kind": row["usage_kind"],
                "evidence_ref": row["evidence_ref"],
                "used_at": row["used_at"],
            }))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise MaterialLibraryError("Invalid Material Library usage record") from exc

    def resolve_physical_locator(self, record: MaterialLibraryRecord) -> Path:
        """Resolve and verify a catalog-owned object without following symlinks."""
        path = self._path(record.physical_locator)
        self._verify_inside(path)
        if path.is_symlink() or not path.is_file():
            raise MaterialLibraryError("Library physical object is unavailable")
        if self._digest(path) != record.asset.file.sha256:
            raise MaterialLibraryError("Library physical object failed content verification")
        return path

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(self._SCHEMA)
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(library_assets)")
            }
            if "source_creation_id" not in columns:
                connection.execute("ALTER TABLE library_assets ADD COLUMN source_creation_id TEXT")
            if "provenance_json" not in columns:
                connection.execute("ALTER TABLE library_assets ADD COLUMN provenance_json TEXT NOT NULL DEFAULT '{}'")
            if "promotion_consent_json" not in columns:
                connection.execute("ALTER TABLE library_assets ADD COLUMN promotion_consent_json TEXT")

    @staticmethod
    def _validate_eligibility(asset: MaterialAsset, store: AttemptMaterialStore) -> None:
        if not _SHA256_RE.fullmatch(asset.file.sha256):
            raise PromotionRejected("Content identity is required for Library promotion")
        if asset.technical.status is not TechnicalStatus.PASSED:
            raise PromotionRejected("Technical inspection must pass before Library promotion")
        try:
            source_path = store.resolve_asset_locator(asset.file.path)
            if (source_path.stat().st_size != asset.file.size
                    or MaterialLibraryCatalog._digest(source_path) != asset.file.sha256):
                raise PromotionRejected("Attempt material content identity does not match its SHA and size")
        except (AttemptMaterialStoreError, OSError) as exc:
            raise PromotionRejected("Attempt material bytes are unavailable") from exc
        source = asset.source
        has_source_evidence = any((source.provider, source.provider_asset_id, source.source_page, source.creator))
        acquisition_evidence = store.read_acquisition_evidence(asset.asset_id)
        if not source.kind.strip() or not has_source_evidence and not acquisition_evidence:
            raise PromotionRejected("Source/provenance evidence is required for Library promotion")
        if asset.rights.status not in {
            RightsStatus.KNOWN, RightsStatus.PUBLIC_DOMAIN,
            RightsStatus.ATTRIBUTION_REQUIRED,
        }:
            raise PromotionRejected("Rights UNKNOWN or RESTRICTED cannot be promoted to the Material Library")
        if asset.rights.status is RightsStatus.KNOWN and not asset.rights.license_name:
            raise PromotionRejected("A verified license name is required for Material Library promotion")
        if not asset.rights.evidence:
            raise PromotionRejected("Verified Rights evidence is required for Material Library promotion")
        if asset.rights.status is RightsStatus.ATTRIBUTION_REQUIRED and not asset.rights.attribution_text:
            raise PromotionRejected("Attribution text is required before promoting this asset")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _record_from_row(self, row: sqlite3.Row) -> MaterialLibraryRecord:
        try:
            payload: dict[str, Any] = {
                "library_asset_id": row["library_asset_id"],
                "scope": {"tenant_id": row["tenant_id"], "creator_id": row["creator_id"]},
                "asset": json.loads(row["asset_json"]),
                "physical_locator": row["physical_locator"],
                "source_creation_id": row["source_creation_id"] if "source_creation_id" in row.keys() else None,
                "source_attempt_id": row["source_attempt_id"],
                "provenance": json.loads(row["provenance_json"]) if "provenance_json" in row.keys() else {},
                "lifecycle_status": row["lifecycle_status"],
                "promotion_consent": (
                    json.loads(row["promotion_consent_json"])
                    if "promotion_consent_json" in row.keys() and row["promotion_consent_json"]
                    else None
                ),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "last_used_at": row["last_used_at"],
            }
            # JSON validation intentionally mirrors the on-disk ContractModel
            # path: enum values, arrays, and ISO timestamps are decoded by the
            # contract boundary rather than coerced ad hoc in the catalog.
            return MaterialLibraryRecord.model_validate_json(json.dumps(payload, ensure_ascii=False))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise MaterialLibraryError("Invalid Material Library record") from exc

    def _stage_object(self, source: Path, target: Path, expected_sha256: str) -> None:
        self._verify_inside(target.parent)
        if target.exists():
            if target.is_symlink() or not target.is_file() or self._digest(target) != expected_sha256:
                raise MaterialLibraryError("Library object path is occupied by invalid content")
            return
        descriptor, temporary_name = tempfile.mkstemp(prefix=".library-", suffix=".tmp", dir=target.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        if self._digest(target) != expected_sha256:
            target.unlink(missing_ok=True)
            raise MaterialLibraryError("Staged library object failed content verification")

    def _path(self, locator: str) -> Path:
        path = PurePosixPath(locator)
        if path.is_absolute() or "\\" in locator or any(part in {"", ".", ".."} for part in locator.split("/")):
            raise MaterialLibraryError("Library locator must be canonical and relative")
        return self.root.joinpath(*path.parts)

    def _verify_inside(self, path: Path) -> None:
        if path.is_symlink():
            raise MaterialLibraryError("Symlinks are not allowed in Material Library paths")
        try:
            path.resolve(strict=False).relative_to(self.root)
        except ValueError as exc:
            raise MaterialLibraryError("Material Library path escapes catalog root") from exc

    @staticmethod
    def _digest(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _validate_token(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
            raise MaterialLibraryError(f"{field_name} contains unsupported characters")


__all__ = ["LibraryScope", "MaterialLibraryCatalog", "MaterialLibraryError", "MaterialLibraryRecord"]
