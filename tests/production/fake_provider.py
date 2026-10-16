"""Local durable receipt counter; never reaches a model or media service."""
import json
from pathlib import Path
import sqlite3

from easel.production.providers.base import ProviderCapabilities, ProviderResult, SubmissionNotSent, SubmissionUncertain


class FakeProvider:
    provider_id = "fixture"
    model = "image"
    mode = "normal"
    capabilities = ProviderCapabilities(query_by_task_id=True, query_by_request_key=True)

    def __init__(self, path: Path, *, fault: str | None = None):
        self.path, self.fault = path, fault
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS received(id INTEGER PRIMARY KEY, request_key TEXT, payload TEXT)")

    @property
    def count(self):
        with sqlite3.connect(self.path) as connection:
            return connection.execute("SELECT COUNT(*) FROM received").fetchone()[0]

    def submit(self, request, *, request_key):
        if self.fault == "before":
            raise SubmissionNotSent()
        with sqlite3.connect(self.path) as connection:
            task = str(connection.execute("INSERT INTO received(request_key,payload) VALUES(?,?)", (request_key, json.dumps(request))).lastrowid)
        if self.fault == "after":
            raise SubmissionUncertain()
        if self.fault == "failed":
            return ProviderResult("failed", task_id=task)
        if self.fault == "pending":
            return ProviderResult("submitted", task_id=task)
        return ProviderResult("succeeded", task_id=task, result={"media_ref": "test-media"})

    def observe(self, *, task_id, request_key):
        if self.fault == "poll":
            raise RuntimeError("not a public diagnostic")
        if self.fault == "not_found":
            return ProviderResult("not_found")
        with sqlite3.connect(self.path) as connection:
            row = connection.execute("SELECT id FROM received WHERE request_key=? ORDER BY id LIMIT 1", (request_key,)).fetchone()
        return ProviderResult("succeeded", task_id=str(row[0]), result={"media_ref": "test-media"}) if row else ProviderResult("not_found")
