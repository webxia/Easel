"""PUB-01: publication is independent of production runs and their grants."""
SQL = r'''
CREATE TABLE publication_drafts (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id),
 output_id TEXT NOT NULL REFERENCES artifacts(id), acceptance_id TEXT NOT NULL,
 media_digest TEXT NOT NULL, output_revision INTEGER NOT NULL,
 platform TEXT NOT NULL CHECK(platform='bilibili'), revision INTEGER NOT NULL DEFAULT 1,
 content_json TEXT NOT NULL CHECK(json_valid(content_json)),
 last_error_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(last_error_json)),
 state TEXT NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','submitted','cancelled')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(acceptance_id,platform)
);
CREATE TABLE publication_attempts (
 id TEXT PRIMARY KEY, draft_id TEXT NOT NULL REFERENCES publication_drafts(id),
 draft_revision INTEGER NOT NULL, confirmation_hash TEXT NOT NULL,
 account_json TEXT NOT NULL CHECK(json_valid(account_json)),
 content_json TEXT NOT NULL CHECK(json_valid(content_json)),
 state TEXT NOT NULL CHECK(state IN ('sending','unknown','verified','failed_before_submit')),
 receipt_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(receipt_json)),
 snapshot_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(snapshot_json)),
 submitted_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(draft_id,draft_revision)
);
'''
