"""Forward-only, transactional SQLite migrations shipped as Python package data."""

MIGRATIONS = {1: r'''
CREATE TABLE profile_refs (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 settings_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(settings_json) AND json_extract(settings_json,'$.schema_version') IS 1),
 created_at TEXT NOT NULL
);
CREATE TABLE directors (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE director_revisions (
 id TEXT PRIMARY KEY, director_id TEXT NOT NULL REFERENCES directors(id), revision INTEGER NOT NULL CHECK(revision>0),
 style_json TEXT NOT NULL CHECK(json_valid(style_json) AND json_extract(style_json,'$.schema_version') IS 1),
 evidence_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(evidence_json)),
 style_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(style_confirmed IN (0,1)),
 trial_artifact_id TEXT REFERENCES artifacts(id), accepted_at TEXT, created_at TEXT NOT NULL,
 UNIQUE(director_id,revision), CHECK(accepted_at IS NULL OR (style_confirmed=1 AND trial_artifact_id IS NOT NULL))
);
CREATE TABLE channels (
 id TEXT PRIMARY KEY, profile_ref TEXT NOT NULL REFERENCES profile_refs(id), name TEXT NOT NULL,
 settings_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(settings_json) AND json_extract(settings_json,'$.schema_version') IS 1),
 default_director_revision TEXT REFERENCES director_revisions(id), archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE channel_directors (
 channel_id TEXT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
 director_id TEXT NOT NULL REFERENCES directors(id), PRIMARY KEY(channel_id,director_id)
);
CREATE TABLE works (
 id TEXT PRIMARY KEY, profile_ref TEXT REFERENCES profile_refs(id), channel_id TEXT REFERENCES channels(id),
 title TEXT NOT NULL, input_text TEXT NOT NULL DEFAULT '', source_session_id TEXT,
 settings_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(settings_json) AND json_extract(settings_json,'$.schema_version') IS 1),
 state TEXT NOT NULL DEFAULT 'discussing' CHECK(state IN ('discussing','awaiting_confirmation','producing','needs_decision','preview_needs_fix','reviewable','cancelled')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), current_plan_revision INTEGER,
 active_run_id TEXT, accepted_output_id TEXT,
 image_limit INTEGER NOT NULL DEFAULT 0 CHECK(image_limit>=0), video_limit INTEGER NOT NULL DEFAULT 0 CHECK(video_limit>=0),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(id,current_plan_revision) REFERENCES plan_revisions(work_id,revision) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(id,active_run_id) REFERENCES runs(work_id,id) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(id,accepted_output_id) REFERENCES artifacts(work_id,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE work_inputs (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id),
 kind TEXT NOT NULL CHECK(kind IN ('text','image','video','audio','document')),
 usage TEXT NOT NULL CHECK(usage IN ('must_use','reference')), source_ref TEXT NOT NULL,
 digest TEXT NOT NULL, original_name TEXT NOT NULL DEFAULT '', text_content TEXT NOT NULL DEFAULT '',
 metadata_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(metadata_json) AND json_extract(metadata_json,'$.schema_version') IS 1),
 created_at TEXT NOT NULL, UNIQUE(work_id,id)
);
CREATE TABLE plan_revisions (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id), revision INTEGER NOT NULL CHECK(revision>0),
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_extract(payload_json,'$.schema_version') IS 1),
 plan_hash TEXT NOT NULL, confirmed_at TEXT, created_at TEXT NOT NULL, UNIQUE(work_id,revision)
);
CREATE TABLE authorization_grants (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id),
 purpose TEXT NOT NULL CHECK(purpose IN ('planning','preview','production')), plan_revision INTEGER, target_ref TEXT,
 services_json TEXT NOT NULL CHECK(json_valid(services_json) AND json_type(services_json)='array'),
 allow_ai INTEGER NOT NULL DEFAULT 0 CHECK(allow_ai IN (0,1)),
 image_limit INTEGER NOT NULL DEFAULT 0 CHECK(image_limit>=0), video_limit INTEGER NOT NULL DEFAULT 0 CHECK(video_limit>=0),
 revoked_at TEXT, created_at TEXT NOT NULL, UNIQUE(work_id,id),
 FOREIGN KEY(work_id,plan_revision) REFERENCES plan_revisions(work_id,revision),
 CHECK(purpose!='production' OR plan_revision IS NOT NULL),
 CHECK(purpose='production' OR (allow_ai=0 AND image_limit=0 AND video_limit=0))
);
CREATE TABLE runs (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id),
 kind TEXT NOT NULL CHECK(kind IN ('planning','production','revision')),
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','waiting_external','needs_decision','paused','succeeded','failed','cancelled','superseded')),
 plan_revision INTEGER, target_ref TEXT, graph_version TEXT NOT NULL, input_fingerprint TEXT NOT NULL,
 owner_id TEXT, owner_epoch INTEGER NOT NULL DEFAULT 0 CHECK(owner_epoch>=0), lease_expires_at REAL,
 cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK(cancel_requested IN (0,1)), revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(work_id,id),
 FOREIGN KEY(work_id,plan_revision) REFERENCES plan_revisions(work_id,revision),
 CHECK(kind='planning' OR plan_revision IS NOT NULL)
);
CREATE UNIQUE INDEX one_active_run ON runs(work_id) WHERE state IN ('pending','running','waiting_external','needs_decision','paused');
CREATE TABLE tasks (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL, run_id TEXT NOT NULL,
 kind TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','waiting_external','retryable_failed','needs_decision','succeeded','failed','cancelled')),
 plan_revision INTEGER, input_fingerprint TEXT NOT NULL,
 payload_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(payload_json) AND json_extract(payload_json,'$.schema_version') IS 1),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)), error_json TEXT CHECK(error_json IS NULL OR json_valid(error_json)),
 owner_epoch INTEGER NOT NULL DEFAULT 0 CHECK(owner_epoch>=0), revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(work_id,run_id,id),
 FOREIGN KEY(work_id,run_id) REFERENCES runs(work_id,id),
 FOREIGN KEY(work_id,plan_revision) REFERENCES plan_revisions(work_id,revision)
);
CREATE TABLE task_dependencies (
 task_id TEXT NOT NULL REFERENCES tasks(id), depends_on TEXT NOT NULL REFERENCES tasks(id),
 PRIMARY KEY(task_id,depends_on), CHECK(task_id!=depends_on)
);
CREATE TABLE operations (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL, run_id TEXT NOT NULL, task_id TEXT NOT NULL, grant_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('IMAGE','VIDEO','VOICE','MODEL')),
 state TEXT NOT NULL DEFAULT 'reserved' CHECK(state IN ('reserved','sending','submitted','unknown','succeeded','failed_after_submit','failed_before_submit','cancelled')),
 input_hash TEXT NOT NULL, request_key TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL, mode TEXT NOT NULL,
 config_version TEXT NOT NULL, request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 provider_task_id TEXT, receipt_json TEXT CHECK(receipt_json IS NULL OR json_valid(receipt_json)), error_code TEXT,
 owner_epoch INTEGER NOT NULL CHECK(owner_epoch>=0), submitted_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), UNIQUE(provider,request_key), UNIQUE(work_id,id),
 FOREIGN KEY(work_id,run_id,task_id) REFERENCES tasks(work_id,run_id,id),
 FOREIGN KEY(work_id,grant_id) REFERENCES authorization_grants(work_id,id)
);
CREATE TABLE artifacts (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id), run_id TEXT, operation_id TEXT,
 kind TEXT NOT NULL, storage_ref TEXT NOT NULL, digest TEXT NOT NULL, size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
 media_type TEXT NOT NULL DEFAULT 'application/octet-stream', displayable INTEGER NOT NULL DEFAULT 0 CHECK(displayable IN (0,1)),
 output_revision INTEGER, quality_state TEXT NOT NULL DEFAULT 'unchecked' CHECK(quality_state IN ('unchecked','needs_fix','passed')),
 metadata_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(metadata_json) AND json_extract(metadata_json,'$.schema_version') IS 1),
 created_at TEXT NOT NULL, UNIQUE(work_id,id), UNIQUE(work_id,output_revision),
 FOREIGN KEY(work_id,run_id) REFERENCES runs(work_id,id), FOREIGN KEY(work_id,operation_id) REFERENCES operations(work_id,id)
);
CREATE TABLE artifact_edges (
 artifact_id TEXT NOT NULL REFERENCES artifacts(id), dependency_id TEXT NOT NULL REFERENCES artifacts(id),
 role TEXT NOT NULL, PRIMARY KEY(artifact_id,dependency_id,role), CHECK(artifact_id!=dependency_id)
);
CREATE TABLE quality_checks (
 id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(id), artifact_digest TEXT NOT NULL,
 check_kind TEXT NOT NULL CHECK(check_kind IN ('technical','semantic')), rule_version TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pass','fail','partial','not_tested')),
 findings_json TEXT NOT NULL CHECK(json_valid(findings_json)), created_at TEXT NOT NULL
);
CREATE TABLE reviews (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL, output_id TEXT NOT NULL, feedback TEXT NOT NULL,
 changes_json TEXT NOT NULL DEFAULT '{"schema_version":1}' CHECK(json_valid(changes_json) AND json_extract(changes_json,'$.schema_version') IS 1),
 created_at TEXT NOT NULL, FOREIGN KEY(work_id,output_id) REFERENCES artifacts(work_id,id)
);
CREATE TABLE acceptances (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL, output_id TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(work_id,output_id) REFERENCES artifacts(work_id,id)
);
CREATE TABLE events (
 work_id TEXT NOT NULL REFERENCES works(id), seq INTEGER NOT NULL CHECK(seq>0), kind TEXT NOT NULL,
 run_id TEXT, work_revision INTEGER NOT NULL CHECK(work_revision>0), actor TEXT NOT NULL,
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), created_at TEXT NOT NULL,
 PRIMARY KEY(work_id,seq), FOREIGN KEY(work_id,run_id) REFERENCES runs(work_id,id)
);
CREATE TABLE command_receipts (
 command_id TEXT PRIMARY KEY, work_id TEXT REFERENCES works(id), request_hash TEXT NOT NULL,
 response_json TEXT NOT NULL CHECK(json_valid(response_json)), created_at TEXT NOT NULL
);
CREATE TRIGGER plan_content_immutable BEFORE UPDATE ON plan_revisions
WHEN NEW.id!=OLD.id OR NEW.work_id!=OLD.work_id OR NEW.revision!=OLD.revision
 OR NEW.payload_json!=OLD.payload_json OR NEW.plan_hash!=OLD.plan_hash OR NEW.created_at!=OLD.created_at
 OR (OLD.confirmed_at IS NOT NULL AND NEW.confirmed_at IS NOT OLD.confirmed_at)
BEGIN SELECT RAISE(ABORT,'plan_immutable'); END;
CREATE TRIGGER work_channel_scope_insert BEFORE INSERT ON works WHEN NEW.channel_id IS NOT NULL
AND NOT EXISTS(SELECT 1 FROM channels WHERE id=NEW.channel_id AND profile_ref=NEW.profile_ref)
BEGIN SELECT RAISE(ABORT,'channel_profile_mismatch'); END;
CREATE TRIGGER work_channel_scope_update BEFORE UPDATE OF channel_id,profile_ref ON works WHEN NEW.channel_id IS NOT NULL
AND NOT EXISTS(SELECT 1 FROM channels WHERE id=NEW.channel_id AND profile_ref=NEW.profile_ref)
BEGIN SELECT RAISE(ABORT,'channel_profile_mismatch'); END;
CREATE TRIGGER channel_default_valid BEFORE UPDATE OF default_director_revision ON channels
WHEN NEW.default_director_revision IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM director_revisions r JOIN channel_directors cd ON cd.director_id=r.director_id
 JOIN directors d ON d.id=r.director_id WHERE r.id=NEW.default_director_revision
 AND cd.channel_id=NEW.id AND r.accepted_at IS NOT NULL AND d.archived=0)
BEGIN SELECT RAISE(ABORT,'director_default_unavailable'); END;
CREATE TRIGGER operation_identity_immutable BEFORE UPDATE ON operations
WHEN NEW.id!=OLD.id OR NEW.work_id!=OLD.work_id OR NEW.run_id!=OLD.run_id OR NEW.task_id!=OLD.task_id
 OR NEW.grant_id!=OLD.grant_id OR NEW.kind!=OLD.kind OR NEW.input_hash!=OLD.input_hash
 OR NEW.request_key!=OLD.request_key OR NEW.provider!=OLD.provider OR NEW.model!=OLD.model
 OR NEW.mode!=OLD.mode OR NEW.config_version!=OLD.config_version OR NEW.request_json!=OLD.request_json
BEGIN SELECT RAISE(ABORT,'operation_identity_immutable'); END;
CREATE TRIGGER task_dependency_same_run BEFORE INSERT ON task_dependencies
WHEN (SELECT run_id FROM tasks WHERE id=NEW.task_id)!=(SELECT run_id FROM tasks WHERE id=NEW.depends_on)
BEGIN SELECT RAISE(ABORT,'cross_run_dependency'); END;
CREATE TRIGGER production_requires_confirmed_plan BEFORE INSERT ON runs
WHEN NEW.kind IN ('production','revision') AND NOT EXISTS(
 SELECT 1 FROM plan_revisions WHERE work_id=NEW.work_id AND revision=NEW.plan_revision AND confirmed_at IS NOT NULL)
BEGIN SELECT RAISE(ABORT,'plan_not_confirmed'); END;
CREATE TRIGGER task_plan_matches_run BEFORE INSERT ON tasks
WHEN NEW.plan_revision IS NOT (SELECT plan_revision FROM runs WHERE id=NEW.run_id)
BEGIN SELECT RAISE(ABORT,'task_plan_mismatch'); END;
CREATE TRIGGER artifact_identity_immutable BEFORE UPDATE ON artifacts
WHEN NEW.id!=OLD.id OR NEW.work_id!=OLD.work_id OR NEW.run_id IS NOT OLD.run_id
 OR NEW.operation_id IS NOT OLD.operation_id OR NEW.storage_ref!=OLD.storage_ref OR NEW.digest!=OLD.digest
 OR NEW.size_bytes!=OLD.size_bytes OR NEW.output_revision IS NOT OLD.output_revision
BEGIN SELECT RAISE(ABORT,'artifact_identity_immutable'); END;
CREATE TRIGGER quality_digest_matches BEFORE INSERT ON quality_checks
WHEN NEW.artifact_digest!=(SELECT digest FROM artifacts WHERE id=NEW.artifact_id)
BEGIN SELECT RAISE(ABORT,'quality_digest_mismatch'); END;
CREATE TRIGGER acceptance_requires_reviewable BEFORE INSERT ON acceptances
WHEN NOT EXISTS(SELECT 1 FROM artifacts WHERE id=NEW.output_id AND work_id=NEW.work_id
 AND output_revision IS NOT NULL AND displayable=1 AND quality_state='passed')
BEGIN SELECT RAISE(ABORT,'output_not_reviewable'); END;
''', 2: r'''
ALTER TABLE works ADD COLUMN deleted_at TEXT;
ALTER TABLE artifacts ADD COLUMN deleted_at TEXT;
CREATE TABLE cleanup_jobs (
 id TEXT PRIMARY KEY, work_id TEXT NOT NULL REFERENCES works(id), artifact_id TEXT NOT NULL UNIQUE REFERENCES artifacts(id),
 storage_ref TEXT NOT NULL, digest TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','deferred','retained','deleted','failed')),
 reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX cleanup_pending ON cleanup_jobs(state,work_id);
''', 3: r'''
-- S6-14 temporary manual review delivery. The baseline FULL-QC condition
-- remains unchanged; only an explicit Creator-accepted, technical-pass
-- artifact with an auditable semantic NOT_TESTED marker may be accepted.
-- An actual semantic FAIL/PARTIAL is never eligible for this bypass.
DROP TRIGGER acceptance_requires_reviewable;
CREATE TRIGGER acceptance_requires_reviewable BEFORE INSERT ON acceptances
WHEN NOT EXISTS (
  SELECT 1 FROM artifacts a WHERE a.id=NEW.output_id AND a.work_id=NEW.work_id
    AND a.output_revision IS NOT NULL AND a.displayable=1
    AND (
      a.quality_state='passed'
      OR (
        NEW.source='explicit_manual_review'
        AND a.quality_state='needs_fix'
        AND EXISTS (SELECT 1 FROM runs r WHERE r.id=a.run_id
                    AND r.work_id=a.work_id AND r.state='succeeded')
        AND EXISTS (SELECT 1 FROM quality_checks q WHERE q.artifact_id=a.id
                    AND q.artifact_digest=a.digest AND q.check_kind='technical'
                    AND q.status='pass')
        AND EXISTS (SELECT 1 FROM quality_checks q WHERE q.artifact_id=a.id
                    AND q.artifact_digest=a.digest AND q.check_kind='semantic'
                    AND q.status='not_tested'
                    AND json_extract(q.findings_json,'$.mode')='manual_review_only')
        AND NOT EXISTS (SELECT 1 FROM quality_checks q WHERE q.artifact_id=a.id
                        AND q.artifact_digest=a.digest AND q.check_kind='semantic'
                        AND q.status IN ('fail','partial'))
      )
    )
)
BEGIN SELECT RAISE(ABORT,'output_not_reviewable'); END;
'''}

from .conversation import SQL as CONVERSATION_SQL
MIGRATIONS[4] = CONVERSATION_SQL

from .publication import SQL as PUBLICATION_SQL
MIGRATIONS[5] = PUBLICATION_SQL


# PUB-01: accepting a completed version must not depend on a later plan's state.
# Keep the technical/manual/known-failure rules; superseded is eligible only
# with immutable evidence that completion preceded supersession.
MIGRATIONS[6] = MIGRATIONS[3].replace(
    "AND r.work_id=a.work_id AND r.state='succeeded')",
    """AND r.work_id=a.work_id AND (r.state='succeeded' OR (
                      r.state='superseded' AND EXISTS (
                        SELECT 1 FROM events done JOIN events replaced
                          ON replaced.run_id=done.run_id AND replaced.work_id=done.work_id
                        WHERE done.work_id=a.work_id AND done.run_id=r.id
                          AND done.kind='run_completed' AND replaced.kind='run_superseded'
                          AND done.seq<replaced.seq))))""",
)

# PUB-01: keep every existing field/identity; only extend the platform constraint.
# Rebuild parent+child together under Store.initialize's single transaction;
# foreign keys stay enabled throughout, including the final foreign_key_check.
MIGRATIONS[7] = PUBLICATION_SQL.replace(
    "CHECK(platform='bilibili')",
    "CHECK(platform IN ('bilibili','douyin','xiaohongshu','kuaishou','weixin-channels'))",
).replace('publication_drafts', 'publication_drafts_next').replace(
    'publication_attempts', 'publication_attempts_next'
) + r'''
INSERT INTO publication_drafts_next SELECT * FROM publication_drafts;
INSERT INTO publication_attempts_next SELECT * FROM publication_attempts;
DROP TABLE publication_attempts;
DROP TABLE publication_drafts;
ALTER TABLE publication_drafts_next RENAME TO publication_drafts;
ALTER TABLE publication_attempts_next RENAME TO publication_attempts;
'''

# Creator review is authoritative for content findings. Retain all QC rows and
# media identities; this migration changes only the acceptance constraint.
MIGRATIONS[8] = r'''
DROP TRIGGER acceptance_requires_reviewable;
CREATE TRIGGER acceptance_requires_reviewable BEFORE INSERT ON acceptances
WHEN NOT EXISTS (
 SELECT 1 FROM artifacts a WHERE a.id=NEW.output_id AND a.work_id=NEW.work_id
 AND a.kind='output' AND a.deleted_at IS NULL AND a.output_revision IS NOT NULL AND a.displayable=1
 AND (
   (a.quality_state='passed' AND NOT EXISTS (
     SELECT 1 FROM quality_checks q JOIN artifacts same ON same.id=q.artifact_id
     WHERE same.work_id=a.work_id AND same.digest=a.digest AND q.artifact_digest=a.digest
     AND q.check_kind='semantic' AND q.status IN ('fail','partial')))
   OR (
     NEW.source='explicit_manual_review' AND a.quality_state IN ('needs_fix','passed')
     AND EXISTS (SELECT 1 FROM works w WHERE w.id=a.work_id AND w.state!='cancelled' AND w.deleted_at IS NULL)
     AND EXISTS (SELECT 1 FROM runs r WHERE r.id=a.run_id AND r.work_id=a.work_id
       AND (r.state='succeeded' OR (r.state='superseded' AND EXISTS (
         SELECT 1 FROM events done JOIN events replaced
         ON replaced.run_id=done.run_id AND replaced.work_id=done.work_id
         WHERE done.work_id=a.work_id AND done.run_id=r.id
         AND done.kind='run_completed' AND replaced.kind='run_superseded' AND done.seq<replaced.seq))))
     AND (SELECT q.status FROM quality_checks q WHERE q.artifact_id=a.id
       AND q.artifact_digest=a.digest AND q.check_kind='technical'
       ORDER BY q.created_at DESC,q.id DESC LIMIT 1)='pass'
   )
 )
)
BEGIN SELECT RAISE(ABORT,'output_not_reviewable'); END;
'''

# A finished output may be reviewed while its *automatic picture-only* repair
# is safely stopped. Mirror WorkService's guard; retain every row and QC result.
_STOPPED_VISUAL_REPAIR = r'''
 r.kind='production' AND r.state='needs_decision' AND r.owner_id IS NULL
 AND r.cancel_requested=0
 AND EXISTS (SELECT 1 FROM works current WHERE current.id=a.work_id AND current.active_run_id=r.id)
 AND NOT EXISTS (SELECT 1 FROM operations op WHERE op.run_id=r.id
   AND op.state IN ('reserved','sending','submitted','unknown'))
 AND (SELECT count(*) FROM tasks t WHERE t.run_id=r.id AND t.state NOT IN ('succeeded','cancelled'))=1
 AND EXISTS (
   SELECT 1 FROM tasks repair JOIN reviews v ON v.id=json_extract(repair.payload_json,'$.review_id')
   WHERE repair.run_id=r.id AND repair.kind='revise' AND repair.state='needs_decision'
   AND json_extract(repair.error_json,'$.code')='visual_material_gap'
   AND json_type(repair.payload_json,'$.creative_visual_repair')='true'
   AND json_extract(repair.payload_json,'$.repair_scope')='visual'
   AND json_type(repair.payload_json,'$.preserve_audio')='true'
   AND json_extract(repair.payload_json,'$.output_id')=a.id
   AND v.work_id=a.work_id AND v.output_id=a.id
   AND EXISTS (SELECT 1 FROM tasks rendered WHERE rendered.run_id=r.id
     AND rendered.kind='render' AND rendered.state='succeeded'
     AND json_extract(rendered.result_json,'$.output_id')=a.id)
   AND EXISTS (SELECT 1 FROM tasks checked WHERE checked.run_id=r.id
     AND checked.kind='quality' AND checked.state='succeeded'
     AND json_extract(checked.result_json,'$.output_id')=a.id
     AND json_extract(checked.payload_json,'$.visual_repair_review_id')=v.id)
 )
'''
MIGRATIONS[9] = MIGRATIONS[8].replace(
    "AND (r.state='succeeded' OR (r.state='superseded'",
    "AND ((" + _STOPPED_VISUAL_REPAIR + ") OR r.state='succeeded' OR (r.state='superseded'",
)
