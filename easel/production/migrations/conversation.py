"""S6-14A additive conversation state; applied only by explicit Store.initialize."""
SQL = r'''
ALTER TABLE works ADD COLUMN creation_context_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(creation_context_json));
ALTER TABLE channels ADD COLUMN creative_basis_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(creative_basis_json));
CREATE TABLE conversation_segments (
 id TEXT PRIMARY KEY, ui_session TEXT NOT NULL, profile_ref TEXT REFERENCES profile_refs(id),
 work_id TEXT REFERENCES works(id), context_json TEXT NOT NULL CHECK(json_valid(context_json)),
 native_session_id TEXT, revoked_at TEXT, created_at TEXT NOT NULL
);
CREATE INDEX conversation_ui ON conversation_segments(ui_session,created_at);
CREATE TABLE conversation_turns (
 id TEXT PRIMARY KEY, segment_id TEXT NOT NULL REFERENCES conversation_segments(id),
 request_hash TEXT NOT NULL, payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
 state TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE conversation_proposals (
 id TEXT PRIMARY KEY, segment_id TEXT NOT NULL REFERENCES conversation_segments(id), kind TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1, body_json TEXT NOT NULL CHECK(json_valid(body_json)),
 body_hash TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'proposed', receipt_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE work_conversation_links (
 work_id TEXT NOT NULL REFERENCES works(id), ui_session TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(work_id,ui_session)
);
CREATE TABLE work_briefs (
 work_id TEXT NOT NULL REFERENCES works(id), revision INTEGER NOT NULL, body_json TEXT NOT NULL CHECK(json_valid(body_json)),
 body_hash TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(work_id,revision)
);
'''
SQL += r'''
CREATE TABLE conversation_imports (
 id TEXT PRIMARY KEY, segment_id TEXT NOT NULL REFERENCES conversation_segments(id), request_hash TEXT NOT NULL,
 state TEXT NOT NULL, result_json TEXT, created_at TEXT NOT NULL
);
'''
