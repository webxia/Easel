"""Replaceable embedding contracts and a local persistent semantic index."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from easel.materials.domain import MaterialAsset
from easel.materials.library import LibraryScope, MaterialLibraryCatalog, MaterialLibraryError, MaterialLibraryRecord


class EmbeddingContract(BaseModel):
    """Complete persisted embedding record and its reproducibility evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    scope: LibraryScope
    library_asset_id: str = Field(min_length=1)
    asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    dimensions: int = Field(gt=0, le=65536)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    vector: tuple[float, ...]
    indexed_at: datetime

    @model_validator(mode="after")
    def vector_matches_dimensions(self) -> EmbeddingContract:
        if len(self.vector) != self.dimensions or not self.vector:
            raise ValueError("vector dimensions do not match embedding contract")
        if any(not math.isfinite(value) for value in self.vector):
            raise ValueError("embedding vector contains a non-finite value")
        if sum(value * value for value in self.vector) == 0:
            raise ValueError("embedding vector must not be zero")
        return self

    @field_validator("indexed_at")
    @classmethod
    def timezone_aware(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("indexed_at must include a timezone")
        return value


class EmbeddingProvider(Protocol):
    """Small replaceable local or remote embedding provider contract."""

    provider_id: str
    model_version: str
    dimensions: int

    def embed(self, text: str) -> Sequence[float]: ...


class SearchMode(str, Enum):
    VECTOR = "VECTOR"
    METADATA_FALLBACK = "METADATA_FALLBACK"


@dataclass(frozen=True)
class SemanticSearchHit:
    record: MaterialLibraryRecord
    score: float
    rank: int


@dataclass(frozen=True)
class SemanticSearchResult:
    hits: tuple[SemanticSearchHit, ...]
    mode: SearchMode
    stale_asset_ids: tuple[str, ...] = ()
    fallback_reason: str | None = None


class SemanticIndexError(MaterialLibraryError):
    """Raised when embedding or persisted-vector contracts are invalid."""


class MaterialSemanticIndex:
    """SQLite-backed vector records scoped to catalog identity.

    The implementation uses exact cosine scoring over persisted JSON vectors.
    This keeps the default install local and dependency-free while allowing an
    interchangeable ANN/vector backend later without changing embedding
    metadata or MaterialAsset contracts.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS semantic_vectors (
            tenant_id TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            library_asset_id TEXT NOT NULL,
            asset_sha256 TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            model_version TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            text_sha256 TEXT NOT NULL,
            vector_json TEXT NOT NULL,
            indexed_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, creator_id, library_asset_id)
        );
        CREATE INDEX IF NOT EXISTS idx_semantic_vectors_scope
            ON semantic_vectors (tenant_id, creator_id);
    """

    def __init__(self, catalog: MaterialLibraryCatalog, database_path: str | Path | None = None):
        self.catalog = catalog
        self.database_path = Path(database_path) if database_path else catalog.root / "semantic-index.db"
        if self.database_path.exists() and self.database_path.is_symlink():
            raise SemanticIndexError("Semantic index database must not be a symlink")
        try:
            self.database_path.resolve(strict=False).relative_to(catalog.root)
        except ValueError as exc:
            raise SemanticIndexError("Semantic index database must be under the Library root") from exc
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(self._SCHEMA)

    def index_record(
        self,
        record: MaterialLibraryRecord,
        provider: EmbeddingProvider,
    ) -> EmbeddingContract:
        self._validate_provider(provider)
        try:
            persisted = self.catalog.get(record.library_asset_id, scope=record.scope)
        except MaterialLibraryError as exc:
            raise SemanticIndexError("Only cataloged assets can be semantically indexed") from exc
        if persisted != record:
            raise SemanticIndexError("Semantic index input differs from the scoped catalog record")
        text = self.semantic_text(record.asset)
        text_sha256 = self._fingerprint(text)
        vector = self._validate_vector(provider.embed(text), provider.dimensions)
        contract = EmbeddingContract(
            scope=record.scope,
            library_asset_id=record.library_asset_id,
            asset_sha256=record.asset.file.sha256,
            provider_id=provider.provider_id,
            model_version=provider.model_version,
            dimensions=provider.dimensions,
            text_sha256=text_sha256,
            vector=vector,
            indexed_at=datetime.now(timezone.utc),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO semantic_vectors (
                    tenant_id, creator_id, library_asset_id, asset_sha256,
                    provider_id, model_version, dimensions, text_sha256,
                    vector_json, indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (tenant_id, creator_id, library_asset_id) DO UPDATE SET
                    asset_sha256=excluded.asset_sha256,
                    provider_id=excluded.provider_id,
                    model_version=excluded.model_version,
                    dimensions=excluded.dimensions,
                    text_sha256=excluded.text_sha256,
                    vector_json=excluded.vector_json,
                    indexed_at=excluded.indexed_at
                """,
                (
                    record.scope.tenant_id,
                    record.scope.creator_id,
                    record.library_asset_id,
                    record.asset.file.sha256,
                    contract.provider_id,
                    contract.model_version,
                    contract.dimensions,
                    contract.text_sha256,
                    json.dumps(contract.vector, separators=(",", ":")),
                    contract.indexed_at.isoformat(),
                ),
            )
        return contract

    def rebuild(
        self,
        scope: LibraryScope,
        provider: EmbeddingProvider,
    ) -> tuple[EmbeddingContract, ...]:
        """Explicitly rebuild or refresh semantic vectors for one scope."""
        return tuple(self.index_record(record, provider) for record in self.catalog.list_scope(scope=scope))

    def invalidate_record(self, library_asset_id: str, *, scope: LibraryScope) -> bool:
        """Remove one stale or withdrawn vector without touching catalog data."""
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM semantic_vectors WHERE tenant_id=? AND creator_id=? AND library_asset_id=?",
                (scope.tenant_id, scope.creator_id, library_asset_id),
            )
        return cursor.rowcount > 0

    def is_stale(self, record: MaterialLibraryRecord, provider: EmbeddingProvider) -> bool:
        self._validate_provider(provider)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT asset_sha256, provider_id, model_version, dimensions, text_sha256
                FROM semantic_vectors WHERE tenant_id=? AND creator_id=? AND library_asset_id=?
                """,
                (record.scope.tenant_id, record.scope.creator_id, record.library_asset_id),
            ).fetchone()
        return (
            row is None
            or row["asset_sha256"] != record.asset.file.sha256
            or row["provider_id"] != provider.provider_id
            or row["model_version"] != provider.model_version
            or row["dimensions"] != provider.dimensions
            or row["text_sha256"] != self._fingerprint(self.semantic_text(record.asset))
        )

    def search(
        self,
        query: str,
        *,
        scope: LibraryScope,
        provider: EmbeddingProvider | None,
        limit: int = 20,
        metadata_filters: dict[str, object] | None = None,
    ) -> SemanticSearchResult:
        if not query.strip():
            raise SemanticIndexError("Semantic search query must not be blank")
        if limit < 1 or limit > 1000:
            raise SemanticIndexError("Semantic search limit must be between 1 and 1000")
        records = self.catalog.metadata_search(scope=scope, **(metadata_filters or {}))
        if provider is None:
            return self._metadata_fallback(query, records, limit, "embedding_provider_disabled")
        try:
            self._validate_provider(provider)
            query_vector = self._validate_vector(provider.embed(query.strip()), provider.dimensions)
        except Exception as exc:
            return self._metadata_fallback(query, records, limit, "embedding_provider_failed")

        rows_by_id: dict[str, sqlite3.Row] = {}
        if records:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM semantic_vectors WHERE tenant_id=? AND creator_id=?",
                    (scope.tenant_id, scope.creator_id),
                ).fetchall()
            rows_by_id = {row["library_asset_id"]: row for row in rows}

        hits: list[tuple[MaterialLibraryRecord, float]] = []
        stale: list[str] = []
        for record in records:
            row = rows_by_id.get(record.library_asset_id)
            if row is None or self.is_stale(record, provider):
                stale.append(record.library_asset_id)
                continue
            try:
                vector = self._validate_vector(json.loads(row["vector_json"]), provider.dimensions)
            except (json.JSONDecodeError, SemanticIndexError):
                stale.append(record.library_asset_id)
                continue
            hits.append((record, self._cosine(query_vector, vector)))
        hits.sort(key=lambda item: (-item[1], item[0].created_at, item[0].library_asset_id))
        return SemanticSearchResult(
            hits=tuple(SemanticSearchHit(record, score, rank) for rank, (record, score) in enumerate(hits[:limit], 1)),
            mode=SearchMode.VECTOR,
            stale_asset_ids=tuple(sorted(stale)),
        )

    @staticmethod
    def semantic_text(asset: MaterialAsset) -> str:
        """Canonical text from existing source/semantic facts and inferences."""
        values: list[str] = []
        semantic = asset.semantic
        if semantic.caption:
            values.append(semantic.caption)
        values.extend(semantic.tags)
        for key, value in sorted(semantic.attributes.items()):
            stable_value = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            values.append(f"{key}: {stable_value}")
        for inference in semantic.inferences:
            for annotation in inference.annotations:
                values.append(f"{annotation.field.value}: {annotation.value}")
        return "\n".join(values).strip()

    def _metadata_fallback(
        self,
        query: str,
        records: tuple[MaterialLibraryRecord, ...],
        limit: int,
        reason: str,
    ) -> SemanticSearchResult:
        query_terms = self._tokens(query)
        scored: list[tuple[MaterialLibraryRecord, float]] = []
        if query_terms:
            for record in records:
                terms = self._tokens(self.semantic_text(record.asset))
                score = len(query_terms & terms) / len(query_terms)
                if score:
                    scored.append((record, score))
        scored.sort(key=lambda item: (-item[1], item[0].created_at, item[0].library_asset_id))
        return SemanticSearchResult(
            hits=tuple(SemanticSearchHit(record, score, rank) for rank, (record, score) in enumerate(scored[:limit], 1)),
            mode=SearchMode.METADATA_FALLBACK,
            fallback_reason=reason,
        )

    @staticmethod
    def _validate_provider(provider: EmbeddingProvider) -> None:
        if not provider.provider_id.strip() or not provider.model_version.strip():
            raise SemanticIndexError("Embedding provider and model version must be named")
        if provider.dimensions < 1 or provider.dimensions > 65536:
            raise SemanticIndexError("Embedding dimensions are invalid")

    @staticmethod
    def _validate_vector(values: Sequence[float], dimensions: int) -> tuple[float, ...]:
        try:
            vector = tuple(float(value) for value in values)
        except (TypeError, ValueError) as exc:
            raise SemanticIndexError("Embedding must contain numeric values") from exc
        if len(vector) != dimensions or not vector:
            raise SemanticIndexError("Embedding dimensions do not match provider contract")
        if any(not math.isfinite(value) for value in vector):
            raise SemanticIndexError("Embedding contains a non-finite value")
        if sum(value * value for value in vector) == 0:
            raise SemanticIndexError("Embedding vector must not be zero")
        return vector

    @staticmethod
    def _cosine(first: tuple[float, ...], second: tuple[float, ...]) -> float:
        dot = sum(left * right for left, right in zip(first, second))
        first_norm = math.sqrt(sum(value * value for value in first))
        second_norm = math.sqrt(sum(value * value for value in second))
        return dot / (first_norm * second_norm)

    @staticmethod
    def _fingerprint(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {item.casefold() for item in re.findall(r"[\w\u3400-\u9fff]+", text) if item}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection


__all__ = [
    "EmbeddingContract",
    "EmbeddingProvider",
    "MaterialSemanticIndex",
    "SearchMode",
    "SemanticIndexError",
    "SemanticSearchHit",
    "SemanticSearchResult",
]
