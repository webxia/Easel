"""V1 catalog adaptation: scoped records, immutable bytes and explicit promotion.

Derived from library.py at 57c8e2ade21af9fb6abccdab3f7ba8e50132314f,
Apache-2.0 (repository LICENSE). V1's content-addressed storage, digest checks,
metadata matching and recorded consent remain. Visibility and current use are
separate; no Attempt/Creation/quote or production state is copied.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from easel.materials.domain import MaterialAsset, MediaType, RightsStatus, TechnicalStatus
from easel.materials.store import MaterialFileStore, MaterialStoreError, canonical_locator, digest_file, reject_symlinks


class MaterialLibraryError(MaterialStoreError):
    pass


class PromotionRejected(MaterialLibraryError):
    pass


class ReferenceProtected(MaterialLibraryError):
    pass


class LibraryVisibility(BaseModel):
    """Existing local owner and optional six-dimension profile identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    owner_id: str = Field(default="local", min_length=1, max_length=128)
    profile_ref: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("owner_id", "profile_ref")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Visibility identity must not be blank")
        return value

    @property
    def profile_key(self) -> str:
        return self.profile_ref or ""

    @property
    def key(self) -> str:
        return json.dumps([self.owner_id, self.profile_ref], ensure_ascii=False, separators=(",", ":"))


class UseContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    work_id: str = Field(min_length=1, max_length=128)
    purpose: Literal["reference", "production"] = "production"
    constraints: dict[str, Any] = Field(default_factory=dict)


class PromotionConsent(BaseModel):
    """Explicit library reuse permission; never inferred from video acceptance."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    authorized: bool
    actor_id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    consented_at: datetime

    @field_validator("actor_id", "purpose")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Consent fields must not be blank")
        return value.strip()

    @field_validator("consented_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Consent must include a timezone")
        return value


class MaterialLibraryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1
    library_asset_id: str
    scope: LibraryVisibility
    asset: MaterialAsset
    physical_locator: str
    source_work_id: str
    input_purpose: Literal["reference", "production"]
    reusable: bool = False
    # Explicit verified owner-wide reuse applies only to imported local materials.
    owner_shared: bool = False
    lifecycle_status: Literal["ACTIVE", "DELETED"] = "ACTIVE"
    promotion_consent: PromotionConsent | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("physical_locator")
    @classmethod
    def relative_locator(cls, value: str) -> str:
        return canonical_locator(value)

    @property
    def asset_ref(self) -> str:
        return self.library_asset_id


class MaterialLibraryUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    reference_id: str
    library_asset_id: str
    work_id: str
    need_ids: tuple[str, ...] = ()
    attribution: dict[str, str] | None = None
    used_at: datetime


class MaterialLibraryCatalog:
    """A separate material catalog, never a second production state authority."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS material_schema(id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS library_assets (
            library_asset_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
            profile_key TEXT NOT NULL, source_work_id TEXT NOT NULL,
            sha256 TEXT NOT NULL, physical_locator TEXT NOT NULL,
            record_json TEXT NOT NULL, lifecycle_status TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS library_scope ON library_assets(owner_id, profile_key);
        CREATE TABLE IF NOT EXISTS library_asset_usage (
            reference_id TEXT NOT NULL, library_asset_id TEXT NOT NULL,
            work_id TEXT NOT NULL, usage_json TEXT NOT NULL,
            PRIMARY KEY(reference_id, library_asset_id, work_id),
            FOREIGN KEY(library_asset_id) REFERENCES library_assets(library_asset_id));
    """

    def __init__(self, root: str | Path):
        supplied = Path(root).expanduser().absolute()
        if any(p.is_symlink() for p in (supplied, *supplied.parents)):
            raise MaterialLibraryError("Catalog root must not contain symlinks")
        supplied.mkdir(parents=True, exist_ok=True)
        self.files = MaterialFileStore(supplied)
        self.root = self.files.root
        self.database_path = self.root / "catalog.db"
        reject_symlinks(self.root, self.database_path)
        with self._connect() as db:
            # V1 catalogs must not be silently initialized/migrated as V2.
            existing = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if existing and "material_schema" not in existing:
                raise MaterialLibraryError("Existing non-V2 catalog requires explicit migration")
            if "material_schema" in existing:
                versions = db.execute("SELECT version FROM material_schema").fetchall()
                if len(versions) != 1 or versions[0][0] != 1:
                    raise MaterialLibraryError("Unsupported material catalog schema")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(self._SCHEMA)
            db.execute("INSERT OR IGNORE INTO material_schema VALUES (1,1)")

    @contextmanager
    def _connect(self):
        reject_symlinks(self.root, self.database_path)
        for suffix in ("-wal", "-shm", "-journal"):
            reject_symlinks(self.root, Path(str(self.database_path) + suffix))
        db = sqlite3.connect(self.database_path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _visible(record: MaterialLibraryRecord, scope: LibraryVisibility, context: UseContext) -> bool:
        if record.lifecycle_status != "ACTIVE" or record.scope.owner_id != scope.owner_id:
            return False
        if record.scope == scope:
            if record.source_work_id == context.work_id:
                return True
            if scope.profile_ref and record.reusable and "current_creation_only" not in record.asset.rights.usage_constraints:
                return True
        return bool(record.scope.profile_ref is None and record.owner_shared and record.reusable
                    and record.promotion_consent is not None and record.promotion_consent.authorized
                    and record.promotion_consent.purpose == "owner_shared_import"
                    and record.asset.source.kind == "local_import"
                    and "current_creation_only" not in record.asset.rights.usage_constraints)

    def register(self, asset: MaterialAsset, source_store: MaterialFileStore, *,
                 scope: LibraryVisibility, context: UseContext) -> MaterialLibraryRecord:
        path = source_store.resolve_asset_locator(asset.file.path)
        if path.stat().st_size != asset.file.size or digest_file(path) != asset.file.sha256:
            raise MaterialLibraryError("Material content identity does not match its bytes")
        # Bytes may be shared physically, but different permissions/provenance
        # never collapse into one record merely because their digests match.
        identity = json.dumps([scope.key, context.work_id, context.purpose,
                               asset.file.sha256, asset.source.model_dump(mode="json"),
                               asset.rights.model_dump(mode="json")], sort_keys=True)
        asset_ref = "mat-" + hashlib.sha256(identity.encode()).hexdigest()
        suffix = path.suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,12}", suffix):
            suffix = ".bin"
        locator = f"objects/{asset.file.sha256}{suffix}"
        self.files.stage_object(path, locator, asset.file.sha256, asset.file.size)
        now = datetime.now(timezone.utc)
        record = MaterialLibraryRecord(library_asset_id=asset_ref, scope=scope, asset=asset,
                    physical_locator=locator, source_work_id=context.work_id, input_purpose=context.purpose,
                    created_at=now, updated_at=now)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # A cleanup of a previously withdrawn record may race staging. Do
            # not register a dangling object; retry can reuse the source bytes.
            if not (self.root / locator).is_file():
                raise MaterialLibraryError("Staged material needs reconciliation before registration")
            existing = db.execute("SELECT record_json FROM library_assets WHERE library_asset_id=?", (asset_ref,)).fetchone()
            if existing:
                previous = MaterialLibraryRecord.model_validate_json(existing[0])
                if previous.lifecycle_status != "ACTIVE":
                    raise MaterialLibraryError("Deleted input cannot be implicitly restored")
                return previous
            db.execute("INSERT INTO library_assets VALUES (?,?,?,?,?,?,?,?)", (
                asset_ref, scope.owner_id, scope.profile_key, context.work_id, asset.file.sha256,
                locator, record.model_dump_json(), record.lifecycle_status))
        return record

    def get(self, library_asset_id: str, *, scope: LibraryVisibility, context: UseContext,
            missing_ok: bool = False) -> MaterialLibraryRecord | None:
        with self._connect() as db:
            row = db.execute("SELECT record_json FROM library_assets WHERE library_asset_id=? AND owner_id=?",
                             (library_asset_id, scope.owner_id)).fetchone()
        record = MaterialLibraryRecord.model_validate_json(row[0]) if row else None
        if record is None or not self._visible(record, scope, context):
            if missing_ok:
                return None
            raise MaterialLibraryError("Material is unavailable in this work and profile scope")
        return record

    def list_scope(self, *, scope: LibraryVisibility, context: UseContext,
                   media_type: MediaType | None = None, technical_status: TechnicalStatus | None = None,
                   rights_status: RightsStatus | None = None, provider: str | None = None,
                   creator: str | None = None, tags_all: tuple[str, ...] = (), tags_any: tuple[str, ...] = (),
                   caption: str | None = None, sha256: str | None = None,
                   limit: int = 100, after_asset_id: str = "") -> tuple[MaterialLibraryRecord, ...]:
        if not 1 <= limit <= 1000:
            raise MaterialLibraryError("Search limit must be between 1 and 1000")
        with self._connect() as db:
            rows = db.execute("SELECT record_json FROM library_assets WHERE owner_id=? AND (profile_key=? OR profile_key='') AND lifecycle_status='ACTIVE' AND library_asset_id>? ORDER BY library_asset_id",
                              (scope.owner_id, scope.profile_key, after_asset_id)).fetchall()
        matches = []
        for row in rows:
            record = MaterialLibraryRecord.model_validate_json(row[0])
            if not self._visible(record, scope, context):
                continue
            asset = record.asset
            if media_type is not None and asset.media_type != media_type:
                continue
            if technical_status is not None and asset.technical.status != technical_status:
                continue
            if rights_status is not None and asset.rights.status != rights_status:
                continue
            if provider is not None and asset.source.provider != provider:
                continue
            if creator is not None and asset.source.creator != creator:
                continue
            if sha256 is not None and asset.file.sha256 != sha256:
                continue
            tags = {v.casefold() for v in asset.semantic.tags}
            if tags_all and not {v.casefold() for v in tags_all} <= tags:
                continue
            if tags_any and not tags.intersection(v.casefold() for v in tags_any):
                continue
            if caption is not None and (asset.semantic.caption or "").casefold() != caption.casefold():
                continue
            matches.append(record)
            if len(matches) == limit:
                break
        return tuple(matches)

    def metadata_search(self, **kwargs) -> tuple[MaterialLibraryRecord, ...]:
        return self.list_scope(**kwargs)

    def resolve_physical_locator(self, record: MaterialLibraryRecord) -> Path:
        path = self.files.resolve_asset_locator(record.physical_locator)
        if path.stat().st_size != record.asset.file.size or digest_file(path) != record.asset.file.sha256:
            raise MaterialLibraryError("Material object failed content verification")
        return path

    def promote(self, asset_ref: str, *, scope: LibraryVisibility, context: UseContext,
                consent: PromotionConsent, owner_shared: bool = False) -> MaterialLibraryRecord:
        record = self.get(asset_ref, scope=scope, context=context)
        if not consent.authorized:
            raise PromotionRejected("Explicit library promotion consent is required")
        if record.source_work_id != context.work_id:
            raise PromotionRejected("Promotion must refer to the source work")
        if owner_shared:
            if (scope.profile_ref is not None or record.asset.source.kind != "local_import"
                    or consent.purpose != "owner_shared_import"):
                raise PromotionRejected("Owner-wide reuse requires explicit consented local import")
        elif scope.profile_ref is None:
            raise PromotionRejected("Unprofiled inputs retain their original work scope")
        self.resolve_physical_locator(record)
        asset = record.asset
        if asset.technical.status is not TechnicalStatus.PASSED:
            raise PromotionRejected("Technical inspection must pass before promotion")
        if asset.rights.status not in {RightsStatus.KNOWN, RightsStatus.PUBLIC_DOMAIN, RightsStatus.ATTRIBUTION_REQUIRED}:
            raise PromotionRejected("Unknown or restricted rights cannot be promoted")
        if not asset.rights.evidence or not any(e.kind.startswith("asset_") for e in asset.rights.evidence):
            raise PromotionRejected("Asset-specific rights evidence is required")
        if asset.rights.status is RightsStatus.KNOWN and not asset.rights.license_name:
            raise PromotionRejected("Verified license name is required")
        if asset.rights.attribution_required and not asset.rights.attribution_text:
            raise PromotionRejected("Exact attribution is required")
        source = asset.source
        if not source.kind.strip() or not any((source.provider, source.provider_asset_id, source.source_page, source.creator)):
            raise PromotionRejected("Source evidence is required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record_json FROM library_assets WHERE library_asset_id=?", (asset_ref,)).fetchone()
            current = MaterialLibraryRecord.model_validate_json(row[0])
            if current.lifecycle_status != "ACTIVE":
                raise PromotionRejected("Deleted material cannot be promoted")
            if current.reusable and current.owner_shared == owner_shared:
                return current
            updated = current.model_copy(update={"reusable": True, "owner_shared": owner_shared,
                "promotion_consent": consent, "updated_at": datetime.now(timezone.utc)})
            db.execute("UPDATE library_assets SET record_json=? WHERE library_asset_id=?", (updated.model_dump_json(), asset_ref))
        return updated

    def record_usage(self, asset_ref: str, *, scope: LibraryVisibility, context: UseContext,
                     reference_id: str, need_ids: tuple[str, ...] = (),
                     attribution: dict[str, str] | None = None) -> MaterialLibraryUsage:
        if not reference_id.strip():
            raise MaterialLibraryError("Reference identity is required")
        record = self.get(asset_ref, scope=scope, context=context)
        self.resolve_physical_locator(record)
        usage = MaterialLibraryUsage(reference_id=reference_id, library_asset_id=asset_ref,
                    work_id=context.work_id, need_ids=tuple(sorted(set(need_ids))), attribution=attribution,
                    used_at=datetime.now(timezone.utc))
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute("SELECT lifecycle_status FROM library_assets WHERE library_asset_id=?", (asset_ref,)).fetchone()
            if not active or active[0] != "ACTIVE":
                raise MaterialLibraryError("Deleted material cannot acquire new references")
            old = db.execute("SELECT usage_json FROM library_asset_usage WHERE reference_id=? AND library_asset_id=? AND work_id=?",
                             (reference_id, asset_ref, context.work_id)).fetchone()
            if old:
                prior = MaterialLibraryUsage.model_validate_json(old[0])
                if prior.attribution != attribution:
                    raise MaterialLibraryError("Reference replay has changed attribution")
                usage = prior.model_copy(update={"need_ids": tuple(sorted(set(prior.need_ids) | set(need_ids)))})
            db.execute("INSERT INTO library_asset_usage VALUES (?,?,?,?) ON CONFLICT(reference_id,library_asset_id,work_id) DO UPDATE SET usage_json=excluded.usage_json",
                       (reference_id, asset_ref, context.work_id, usage.model_dump_json()))
        return usage

    def usage_for_asset(self, asset_ref: str, *, scope: LibraryVisibility, context: UseContext) -> tuple[MaterialLibraryUsage, ...]:
        self.get(asset_ref, scope=scope, context=context)
        with self._connect() as db:
            rows = db.execute("SELECT usage_json FROM library_asset_usage WHERE library_asset_id=? ORDER BY work_id,reference_id", (asset_ref,)).fetchall()
        return tuple(MaterialLibraryUsage.model_validate_json(row[0]) for row in rows)

    def release_reference(self, asset_ref: str, reference_id: str, *, scope: LibraryVisibility, context: UseContext) -> None:
        """Called only after the work service authorizes the precise deletion."""
        self.get(asset_ref, scope=scope, context=context)
        with self._connect() as db:
            db.execute("DELETE FROM library_asset_usage WHERE library_asset_id=? AND reference_id=? AND work_id=?",
                       (asset_ref, reference_id, context.work_id))

    def delete(self, asset_ref: str, *, scope: LibraryVisibility, context: UseContext) -> None:
        """Withdraw only an unreferenced source record; keep bytes for reconciliation.

        Work/output deletion releases references explicitly. Shared objects and
        inbox originals are never deleted by this operation.
        """
        record = self.get(asset_ref, scope=scope, context=context)
        if record.source_work_id != context.work_id:
            raise ReferenceProtected("Only the source work can withdraw material")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM library_asset_usage WHERE library_asset_id=? LIMIT 1", (asset_ref,)).fetchone():
                raise ReferenceProtected("Material is still referenced by a retained version or input")
            deleted = record.model_copy(update={"lifecycle_status": "DELETED", "updated_at": datetime.now(timezone.utc)})
            db.execute("UPDATE library_assets SET lifecycle_status='DELETED', record_json=? WHERE library_asset_id=?",
                       (deleted.model_dump_json(), asset_ref))

    def collect_deleted(self) -> tuple[str, ...]:
        """Explicit reconciliation after authorized reference release.

        Only catalog-owned objects named by withdrawn records are considered;
        this never scans inboxes or old libraries. A retained record/reference
        of any work protects the shared bytes. Production must retain its
        reference before using a handle and defer release for in-flight work.
        """
        removed = []
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            locators = db.execute("SELECT DISTINCT physical_locator FROM library_assets WHERE lifecycle_status='DELETED'").fetchall()
            for (locator,) in locators:
                active = db.execute("SELECT 1 FROM library_assets WHERE physical_locator=? AND lifecycle_status='ACTIVE' LIMIT 1", (locator,)).fetchone()
                referenced = db.execute("SELECT 1 FROM library_assets a JOIN library_asset_usage u ON u.library_asset_id=a.library_asset_id WHERE a.physical_locator=? LIMIT 1", (locator,)).fetchone()
                if active or referenced:
                    continue
                path = self.root / canonical_locator(locator)
                reject_symlinks(self.root, path)
                if not locator.startswith("objects/"):
                    raise MaterialLibraryError("Only catalog objects can be collected")
                if path.exists():
                    try:
                        path.unlink()
                    except OSError:
                        continue  # Keep a Windows in-use file for later reconciliation.
                removed.append(locator)
        return tuple(removed)
