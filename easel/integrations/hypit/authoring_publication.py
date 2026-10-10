"""Validate an isolated native Authoring candidate and conditionally publish it.

The Attempt owns one durable intent. Recovery resumes only that checked file
set; model repair, media execution and fresh derivation are separate operations.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from easel.integrations.output_receipts import OutputReceiptError
from .errors import HypitIntegrationError
from . import native_source

SCHEMA = "native-authoring-publication@1"
AUTHOR = "productions/easel-authoring/authors/main.svml"
RUN = "productions/easel-authoring/runs/main.svrun"
SELECTION = "productions/easel-authoring/material-selection.json"
SIDECAR = "productions/easel-authoring/runs/main.easel.json"
SUPPORT = tuple("packages/audio-mix/" + name for name in ("package.json", "activation.mjs", "envelope.mjs"))
TARGETS = frozenset((AUTHOR, RUN, SIDECAR, SELECTION, *SUPPORT))
EXCLUDED = frozenset((".easel", ".hypit", ".git"))
MAX_FILES = 6000
MAX_WORKSPACE_BYTES = 4 * 1024 ** 3


class AuthoringPublicationError(OutputReceiptError):
    """Local integrity/IO/CAS failure. Retain intent and never repair with a model."""



@contextmanager
def frozen_evidence(native=True):
    """Read existing trusted inputs, separately from validating model content."""
    try:
        yield
    except (OSError, ValueError, KeyError) as exc:
        if not native:
            raise
        raise AuthoringPublicationError("Frozen Authoring evidence is unavailable or changed") from exc

def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _safe(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or "\\" in relative:
        raise AuthoringPublicationError("Authoring path is not a relative workspace path")
    if any(part in {"", ".", ".."} for part in relative.split("/")):
        raise AuthoringPublicationError("Authoring path is not normalized")
    return native_source._safe(root, Path(root) / relative)


def _put(root, relative, raw):
    path = _safe(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".candidate-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        _safe(root, relative)
        os.replace(temporary, path)
        temporary = None
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _files(root):
    """Complete bounded file set, excluding only existing execution/journal caches."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise AuthoringPublicationError("Authoring workspace is unavailable")
    result, total = {}, 0
    for directory, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in EXCLUDED)
        for name in directories:
            if (Path(directory) / name).is_symlink():
                raise AuthoringPublicationError("Authoring dependencies contain a symlink")
        for name in sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            _safe(root, relative)
            before = path.stat()
            if not stat.S_ISREG(before.st_mode):
                raise AuthoringPublicationError("Authoring dependency is not a regular file")
            total += before.st_size
            if len(result) >= MAX_FILES or total > MAX_WORKSPACE_BYTES:
                raise AuthoringPublicationError("Authoring workspace exceeds fixed snapshot capacity")
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while block := stream.read(1024 * 1024):
                    digest.update(block)
            after = path.stat()
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise AuthoringPublicationError("Authoring dependency changed during capture")
            result[relative] = "sha256:" + digest.hexdigest()
    return result


def _metadata(attempt):
    # All actual Attempt inputs are fenced during a publication. Only shared
    # projection/history fields and this operation's own intent are excluded.
    ignored = {"history", "updated_at", "status", "authoring_task", "pending_authoring_publication"}
    return native_source.digest({key: value for key, value in attempt.items() if key not in ignored})


def _domain_payload(attempt):
    from easel.integrations.material_layer import PlanningIntegration, MaterialGateIntegration, ProductionAuthoringIntegration
    from easel.integrations.material_recovery import director_shot_choices
    from easel.materials.store import AttemptMaterialStore
    from . import service
    from .handoff import load_frozen_creative_mode, resolve_handoff, verify_handoff_directory

    root = service._workspace(attempt)
    _, _, handoff_hash = resolve_handoff(attempt["creation_id"], attempt["handoff"]["handoff_id"])
    if handoff_hash != attempt["handoff"]["hash"]:
        raise AuthoringPublicationError("Registered Handoff differs from this Attempt")
    verify_handoff_directory(root / "handoff", handoff_hash)
    planning = PlanningIntegration().load(attempt)
    plan, bundle, readiness = MaterialGateIntegration().assert_ready(
        attempt, _validated_planning=planning)
    integration = ProductionAuthoringIntegration()
    store = AttemptMaterialStore(root)
    _, mode_hash = load_frozen_creative_mode(attempt)
    retry = attempt.get("retry_source", {})
    if retry:
        original = service.get_film_attempt(retry["attempt_id"])
        if service._execution_fingerprint(original)["sha256"] != retry["fingerprint"]:
            raise AuthoringPublicationError("Original retry checkpoint changed")
    payload = {
        "creation_id": attempt["creation_id"], "attempt_id": attempt["attempt_id"],
        "handoff": attempt["handoff"], "mode_sha256": mode_hash,
        "result_protocols": attempt.get("result_protocols"), "production_request": attempt.get("production_request"),
        "revision_feedback": attempt.get("revision_feedback"),
        "retry_source": {key: retry.get(key) for key in ("attempt_id", "build_id", "fingerprint")} if retry else None,
        "plan": plan.model_dump(mode="json"), "bundle": bundle.model_dump(mode="json"),
        "readiness": readiness.model_dump(mode="json"),
        "planning": {key: planning[key] for key in ("script", "scenes", "treatment", "truth_ledger")},
        "director": director_shot_choices(attempt, plan),
        "creator_selection": integration.accepted_combination(attempt, plan, bundle, store),
        "qualified_assets": integration._qualified_authoring_assets_from_ready(attempt, plan, bundle),
    }
    return native_source.digest(payload)


def _domain(attempt):
    try:
        return _domain_payload(attempt)
    except HypitIntegrationError as exc:
        raise AuthoringPublicationError("Frozen Authoring domain evidence cannot be verified") from exc


def require_no_pending(attempt):
    from . import service
    current = service.get_film_attempt(attempt["attempt_id"])
    if current.get("pending_authoring_publication"):
        raise AuthoringPublicationError("Authoring publication is incomplete; resume it before consuming these files")


def _manifest(raw):
    def pairs(values):
        output = {}
        for key, value in values:
            if key in output:
                raise ValueError("duplicate property")
            output[key] = value
        return output
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=lambda text: (_ for _ in ()).throw(ValueError(text)))
    except (UnicodeError, ValueError) as exc:
        raise HypitIntegrationError("Easel Run manifest 必须是完整、唯一键的 JSON") from exc
    if not isinstance(value, dict):
        raise HypitIntegrationError("Easel Run manifest 必须是对象")
    return value


def _run_identity(attempt, plan, bundle, readiness):
    return {
        "schema": "easel-authoring-svrun@1", "creation_id": attempt["creation_id"],
        "attempt_id": attempt["attempt_id"], "plan_id": plan.plan_id,
        "plan_revision": readiness.plan_revision, "bundle_id": bundle.bundle_id,
        "bundle_revision": bundle.revision, "readiness_revision": readiness.bundle_revision,
        "authoring_source": "../authors/main.svml", "material_selection": "../material-selection.json",
        "status": "AUTHORING_READY", "publication_allowed": False,
    }


def _check_manifest(raw, attempt, plan, bundle, readiness):
    value = _manifest(raw)
    expected = _run_identity(attempt, plan, bundle, readiness)
    if any(type(value.get(key)) is not type(item) or value.get(key) != item for key, item in expected.items()):
        raise HypitIntegrationError("Easel Run manifest 冻结身份或禁止发布边界不一致")
    if not isinstance(value.get("build"), dict) or value["build"].get("enabled") is not False:
        raise HypitIntegrationError("Easel Run manifest 必须停在 Hypit Build 之前")
    return value


def assert_run_current(attempt, root, run_path, plan, bundle, readiness):
    if run_path != RUN:
        raise HypitIntegrationError("当前 native profile 只接纳固定 Authoring Run")
    raw = _safe(root, SIDECAR).read_bytes()
    _check_manifest(raw, attempt, plan, bundle, readiness)
    _, run, _ = native_source.parse_run(_safe(root, RUN), workspace=root)
    if (run.get("author") != {"source": "../authors/main.svml"}
            or run.get("targets") != [{"output": "final.video"}]
            or any(run.get(key) for key in ("imports", "candidates", "satisfactions"))):
        raise HypitIntegrationError("原生 Run 与已验证的 Easel identity manifest 不一致")


def _derive(attempt, root, integration, parser):
    from easel.materials.store import AttemptMaterialStore
    from .music import install_music_component

    with frozen_evidence():
        plan, bundle, readiness = integration.gate.assert_ready(attempt)
    doc = native_source.parse_file(root / AUTHOR, workspace=root, identity=parser, require_support=False)
    source = integration.compile_narration(attempt, doc.source.text, _root=root, _document=doc)
    if source != doc.source.text:
        _put(root, AUTHOR, source.encode("utf-8"))
        doc = native_source.parse_file(root / AUTHOR, workspace=root, identity=parser, require_support=False)
    if any(entry["from"] == "@easel/audio-mix@1" for entry in doc.imports):
        install_music_component(root)
    doc = native_source.parse_file(root / AUTHOR, workspace=root, identity=parser)
    sidecar = _safe(root, SIDECAR)
    if sidecar.exists():
        assert_run_current(attempt, root, RUN, plan, bundle, readiness)
    else:
        raw = _safe(root, RUN).read_bytes()
        _check_manifest(raw, attempt, plan, bundle, readiness)
        markup = ('<?svml using="@hypit/run-markup@1"?>\n<svrun version="1">\n'
                  '  <author source="../authors/main.svml"/>\n  <target output="final.video"/>\n</svrun>\n')
        _put(root, SIDECAR, raw)
        _put(root, RUN, markup.encode("utf-8"))
    selection = _manifest(_safe(root, SELECTION).read_bytes())
    if selection.get("status") == "PENDING_PRODUCTION_SELECTION" and selection.get("assets") == []:
        store = AttemptMaterialStore(root)
        declared = {node.literal("src") for node in doc.iter()
                    if node.module == "@hypit/media" and node.local_name in {"Image", "Video", "Audio"}}
        records = []
        for asset in bundle.assets:
            src = store.hypit_source_path(asset, AUTHOR)
            if src not in declared:
                continue
            needs = integration._qualified_need_ids(plan, bundle, asset, store=store, attempt=attempt)
            if not needs:
                raise HypitIntegrationError("SVML 素材缺少当前合格 Need/Match")
            records.append({"asset_id": asset.asset_id, "media_type": asset.media_type.value, "src": src,
                            "mime": asset.file.mime, "sha256": asset.file.sha256, "qualified_need_ids": list(needs)})
        if {row["src"] for row in records} != declared:
            raise HypitIntegrationError("SVML 引用了当前 MaterialBundle 以外的素材")
        selection.update(assets=records, status="SELECTED")
        _put(root, SELECTION, _json(selection))
    validated = integration._validate_authored_selection(attempt, RUN, _root=root, _document=doc)
    _put(root, SELECTION, validated["selection_bytes"])
    return doc, validated["patch"]


def _admit(attempt, doc):
    from . import service, native_revision
    from easel.integrations.material_layer import ProductionAuthoringIntegration, MaterialGateIntegration

    service._assert_composition_revision(attempt, doc)
    service._assert_local_video_trim_ranges(attempt, doc)
    if not attempt.get("revision_feedback"):
        with frozen_evidence():
            plan, _, _ = MaterialGateIntegration().assert_ready(attempt)
        required = {need.need_id for need in plan.needs
                    if need.importance.value == "required" and need.media_type.value in {"image", "video"}}
        native_revision.expression_uses(doc, required_need_ids=required)


def _copy(root, candidate, before):
    for name, expected in before.items():
        source, destination = _safe(root, name), _safe(candidate, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    if _files(candidate) != before or _files(root) != before:
        raise AuthoringPublicationError("Workspace changed while constructing the isolated candidate")


def _candidate(root, intent):
    directory = _safe(root, intent["staging"])
    if not directory.is_dir():
        raise AuthoringPublicationError("Checked Authoring candidate is missing")
    if _files(directory) != intent["after_files"]:
        raise AuthoringPublicationError("Checked Authoring candidate dependencies changed")
    for row in intent["targets"]:
        if row["before"] is not None:
            original = _safe(root, intent["originals"] + "/" + row["path"])
            if _sha(original.read_bytes()) != row["before"]:
                raise AuthoringPublicationError("Captured original Authoring bytes changed")
    return directory


def _prefix(root, intent):
    current = _files(root)
    names = {row["path"] for row in intent["targets"]}
    fixed = {name: sha for name, sha in intent["before_files"].items() if name not in names}
    if {name: sha for name, sha in current.items() if name not in names} != fixed:
        raise AuthoringPublicationError("An Authoring dependency was added, removed or changed")
    unfinished = False
    for row in intent["targets"]:
        actual = current.get(row["path"])
        if actual == row["after"]:
            if unfinished:
                raise AuthoringPublicationError("Authoring files do not match this publication's ordered prefix")
        elif actual == row["before"]:
            unfinished = True
        else:
            raise AuthoringPublicationError("Another writer changed an Authoring publication target")
    return current


def _publish_file(root, row, raw):
    current = _safe(root, row["path"])
    actual = _sha(current.read_bytes()) if current.exists() else None
    if actual != row["before"]:
        raise AuthoringPublicationError("Authoring target changed immediately before replacement")
    if _sha(raw) != row["after"]:
        raise AuthoringPublicationError("Authoring candidate bytes no longer match the check")
    _put(root, row["path"], raw)


def _resume(attempt, root, intent):
    from . import service

    if (not isinstance(intent, dict) or intent.get("schema") != SCHEMA
            or intent.get("attempt_id") != attempt["attempt_id"]
            or intent.get("intent_sha256") != native_source.digest({key: value for key, value in intent.items() if key != "intent_sha256"})
            or any(row["path"] not in TARGETS for row in intent.get("targets", []))):
        raise AuthoringPublicationError("Authoring publication intent is invalid")
    if native_source.installed_parser() != intent["parser"]:
        raise AuthoringPublicationError("The parser used to check this candidate changed")
    if _metadata(attempt) != intent["metadata"] or _domain(attempt) != intent["domain"]:
        raise AuthoringPublicationError("Authoring context changed before publication")
    candidate = _candidate(root, intent)
    current = _prefix(root, intent)
    for row in intent["targets"]:
        if current.get(row["path"]) == row["after"]:
            continue
        live = service.get_film_attempt(attempt["attempt_id"])
        if _metadata(live) != intent["metadata"] or live.get("pending_authoring_publication") != intent:
            raise AuthoringPublicationError("Authoring publication ownership changed")
        _prefix(root, intent)
        _publish_file(root, row, _safe(candidate, row["path"]).read_bytes())
    if _files(root) != intent["after_files"] or _domain(service.get_film_attempt(attempt["attempt_id"])) != intent["domain"]:
        raise AuthoringPublicationError("Published files or domain context changed before registration")

    def finish(item):
        live = {"creation_id": attempt["creation_id"], **item}
        if (live.get("pending_authoring_publication") != intent or _metadata(live) != intent["metadata"]
                or live.get("authoring_status") != "AUTHORING_RUNNING"):
            raise AuthoringPublicationError("Authoring state changed before final registration")
        # Recheck inside the Creation CAS, after waiting for its lock.
        if (_files(root) != intent["after_files"] or _domain(live) != intent["domain"]
                or native_source.installed_parser() != intent["parser"]):
            raise AuthoringPublicationError("Published dependencies or authority changed at final registration")
        changed = {**item, **copy.deepcopy(intent["patch"])}
        changed.pop("pending_authoring_publication", None)
        changed.pop("native_authoring_validation", None)
        if changed.get("cost", {}).get("approved") or changed.get("plan", {}).get("status") == "ready":
            changed = service._invalidate_if_unsubmitted(changed)
        return service._event(changed, "authoring_ready", run_path=RUN,
                              authoring_sha256=changed["authoring"]["authoring_sha256"],
                              publication_id=intent["publication_id"])
    return service._save_attempt(attempt["attempt_id"], finish)



# Exact diagnostics from the fixed 0.2.7 source parsers / authored graph.
# CLI_ERROR also contains installation and internal failures; never infer
# repair authority from its prose or a broad code prefix.
SOURCE_DIAGNOSTICS = frozenset("""
SOURCE_HEADER_DUPLICATE SOURCE_HEADER_FRONTEND SOURCE_HEADER_INVALID SOURCE_HEADER_MISSING SOURCE_HEADER_UNCLOSED
MARKUP_ATTRIBUTE MARKUP_ATTRIBUTE_DUPLICATE MARKUP_CLOSE MARKUP_CLOSE_MISMATCH MARKUP_COMMENT
MARKUP_ELEMENT_UNCLOSED MARKUP_ENTITY MARKUP_IMPORT MARKUP_IMPORT_ALIAS MARKUP_IMPORT_KIND
MARKUP_IMPORT_SOURCE_ALIAS MARKUP_NAME MARKUP_OPEN MARKUP_REFERENCE MARKUP_ROOT MARKUP_ROOT_ATTRIBUTE
MARKUP_ROOT_CLOSE MARKUP_TRAILING MARKUP_ALIAS_DUPLICATE MARKUP_BODY_TEXT MARKUP_IMPORT_AFTER_BODY
MARKUP_UNKNOWN_SURFACE MARKUP_RAW_SELF_CLOSING MARKUP_RECORD_DUPLICATE MARKUP_COMPONENT_DUPLICATE
MARKUP_SOURCE_EXPORT_COLLISION MARKUP_SURFACE_COLLISION MARKUP_ROOT_UNCLOSED
SVS_COMMENT_UNCLOSED SVS_PROPERTY SVS_PROPERTY_COLON SVS_PROPERTY_DUPLICATE SVS_PROPERTY_SEMICOLON
SVS_ROOT SVS_ROOT_UNCLOSED SVS_RULE SVS_RULE_DUPLICATE SVS_RULE_OPEN SVS_RULE_UNCLOSED
SVS_SHEET_ATTRIBUTE SVS_SHEET_ATTRIBUTE_DUPLICATE SVS_SHEET_ID SVS_TRAILING SVS_VALUE_EMPTY
SVS_VALUE_STRUCTURED SVS_VERSION RUN_ATTRIBUTE RUN_AUTHOR_MISSING RUN_AUTHOR_ORDER RUN_CHILD
RUN_DUPLICATE RUN_FRAGMENT_INPUT RUN_FRAGMENT_REF RUN_IMPORT_ORDER RUN_MEDIA_TYPE RUN_ROOT
RUN_SATISFACTION_DUPLICATE RUN_TARGETS RUN_TEXT RUN_TRAILING RUN_TYPE RUN_VERSION
AUTHOR_COMPONENT_CYCLE AUTHOR_INPUT_TYPE_MISMATCH DUPLICATE_AUTHOR_COMPONENT INVALID_AUTHOR_REFERENCE
UNKNOWN_AUTHOR_COMPONENT UNKNOWN_AUTHOR_OUTPUT UNKNOWN_AUTHOR_RECORD
""".split())


def check_authoring(client, root, run):
    """Machine-protocol failures retain the candidate; only known source diagnostics repair."""
    from .errors import HypitCLIError
    try:
        # Actual CLI uses the shared strict JSON decoder. External test doubles
        # implement the same machine contract through their ordinary check method.
        check = getattr(client, "check_native", client.check)(root, run)
    except HypitCLIError as exc:
        payload = exc.payload
        error = payload.get("error") if isinstance(payload, dict) else None
        source_failure = (
            exc.failure_kind is None and exc.returncode == 1
            and isinstance(payload, dict) and payload.get("format") == "hypit.cli-error@1"
            and payload.get("ok") is False and isinstance(error, dict)
            and isinstance(error.get("code"), str) and error["code"] in SOURCE_DIAGNOSTICS
            and isinstance(error.get("message"), str) and bool(error["message"].strip()))
        if source_failure:
            raise
        raise AuthoringPublicationError("Hypit check failed locally or returned an unclassified diagnostic; retain the original candidate") from exc
    if (not isinstance(check, dict) or check.get("format") != "hypit.cli-check@1"
            or check.get("ok") is not True or check.get("sourceKind") != "run"
            or any(not isinstance(check.get(key), str) or not check[key].strip() for key in ("run", "author", "frontend"))
            or check.get("targets") != ["final.video"]
            or any(type(check.get(key)) is not int or check[key] != value
                   for key, value in (("targetCount", 1), ("candidates", 0), ("satisfactions", 0)))
            or ("historicalOutputCount" in check and (type(check["historicalOutputCount"]) is not int
                                                       or check["historicalOutputCount"] != 0))):
        raise AuthoringPublicationError("Hypit check returned an invalid fixed Run result")
    return check

def complete(attempt_id, *, cli=None):
    from . import service
    from .secrets import SecretRedactor
    from easel.integrations.material_layer import ProductionAuthoringIntegration

    attempt = service.get_film_attempt(attempt_id)
    root = service._workspace(attempt)
    try:
        lock = _safe(root, ".easel/authoring-publication.lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open("a+b") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            attempt = service.get_film_attempt(attempt_id)
            pending = attempt.get("pending_authoring_publication")
            if pending:
                return _resume(attempt, root, pending)
            if attempt.get("authoring_status") == "AUTHORING_READY":
                validate_current(attempt, RUN)
                return attempt
            if (attempt.get("authoring_status") != "AUTHORING_RUNNING"
                    or attempt.get("execution_status") not in {"BLOCKED", "NOT_SUBMITTED"}
                    or attempt.get("build", {}).get("build_id")):
                raise HypitIntegrationError("Attempt 未处于可交接的 Authoring 运行状态")
            recovery = attempt.get("native_authoring_validation")
            if not recovery:
                def begin_validation(item):
                    if item.get("authoring_status") != "AUTHORING_RUNNING":
                        raise AuthoringPublicationError("Authoring status changed before local validation")
                    return service._event({**item, "native_authoring_validation": {"schema": SCHEMA, "input_files": None}},
                                          "native_authoring_validation_started")
                attempt = service._save_attempt(attempt_id, begin_validation)
                recovery = attempt["native_authoring_validation"]
            before = _files(root)
            if recovery.get("input_files") is not None and recovery["input_files"] != before:
                raise AuthoringPublicationError("Captured model Authoring files changed before local recovery")
            if recovery.get("input_files") is None:
                def bind_inputs(item):
                    if item.get("native_authoring_validation") != recovery:
                        raise AuthoringPublicationError("Authoring local validation ownership changed")
                    return service._event({**item, "native_authoring_validation": {"schema": SCHEMA, "input_files": before}},
                                          "native_authoring_inputs_captured")
                attempt = service._save_attempt(attempt_id, bind_inputs)
            parser = native_source.installed_parser()
            metadata, domain = _metadata(attempt), _domain(attempt)
            if RUN not in before or AUTHOR not in before or SELECTION not in before:
                raise HypitIntegrationError("Authoring 缺少完整的必需产物")
            publication_id = uuid.uuid4().hex
            staging = ".easel/native-authoring/" + publication_id + "/workspace"
            originals = ".easel/native-authoring/" + publication_id + "/originals"
            candidate = _safe(root, staging)
            candidate.mkdir(parents=True)
            _copy(root, candidate, before)
            for name in TARGETS & before.keys():
                _put(root, originals + "/" + name, _safe(candidate, name).read_bytes())
            integration = ProductionAuthoringIntegration()
            doc, patch = _derive(attempt, candidate, integration, parser)
            _admit(attempt, doc)
            after = _files(candidate)
            if any(before.get(name) != after.get(name) for name in before.keys() | after.keys() if name not in TARGETS):
                raise AuthoringPublicationError("Candidate derivation changed a non-owned dependency")
            with frozen_evidence():
                client = service._cli(cli)
            check = check_authoring(client, candidate, candidate / RUN)
            if _files(candidate) != after:
                raise AuthoringPublicationError("Static check changed its input files")
            live = service.get_film_attempt(attempt_id)
            if _files(root) != before or _metadata(live) != metadata or _domain(live) != domain:
                raise AuthoringPublicationError("Authoring input changed while checking the isolated candidate")
            if native_source.installed_parser() != parser:
                raise AuthoringPublicationError("Parser changed while checking the candidate")
            authoring_hash, run_hash, dependency_hash, files = service._authoring_file_hash(candidate, candidate / RUN)
            receipt = {"schema": SCHEMA, "publication_id": publication_id, "parser": parser,
                       "source": doc.source_identity, "domain": domain}
            patch.update(authoring_status="AUTHORING_READY", authoring={
                **attempt.get("authoring", {}), "status": "ready", "run_path": RUN,
                "check": SecretRedactor.redact(check), "authoring_sha256": authoring_hash,
                "run_sha256": run_hash, "dependencies_sha256": dependency_hash, "files": files,
                "completed_at": service._now(), "native_publication": receipt})
            retry = attempt.get("retry_source", {})
            if retry.get("status") == "AUTHORING_REPAIR_REQUIRED":
                patch["retry_source"] = {**retry, "status": "READY"}
            order = {SIDECAR: 1, RUN: 2, SELECTION: 3}
            names = sorted((name for name in TARGETS if before.get(name) != after.get(name)),
                           key=lambda name: (order.get(name, 0), name))
            targets = [{"path": name, "before": before.get(name), "after": after[name]} for name in names]
            intent = {"schema": SCHEMA, "publication_id": publication_id, "attempt_id": attempt_id,
                      "staging": staging, "originals": originals, "before_files": before, "after_files": after,
                      "targets": targets, "metadata": metadata, "domain": domain, "parser": parser, "patch": patch}
            intent["intent_sha256"] = native_source.digest(intent)
            def prepare(item):
                current = {"creation_id": attempt["creation_id"], **item}
                if _metadata(current) != metadata or current.get("pending_authoring_publication"):
                    raise AuthoringPublicationError("Authoring state changed before intent registration")
                return service._event({**item, "pending_authoring_publication": intent},
                                      "authoring_publication_prepared", publication_id=publication_id)
            attempt = service._save_attempt(attempt_id, prepare)
            return _resume(attempt, root, intent)
    except OSError as exc:
        raise AuthoringPublicationError("Authoring storage failed; recover the existing local publication") from exc


def validate_current(attempt, run_path, *, integration=None):
    from . import service
    from easel.integrations.material_layer import ProductionAuthoringIntegration

    require_no_pending(attempt)
    current = service.get_film_attempt(attempt["attempt_id"])
    root = service._workspace(current)
    receipt = current.get("authoring", {}).get("native_publication")
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA or run_path != RUN:
        raise AuthoringPublicationError("Native Authoring has no complete publication receipt")
    try:
        if receipt.get("parser") != native_source.installed_parser() or receipt.get("domain") != _domain(current):
            raise AuthoringPublicationError("Published native Authoring context changed")
        expected = {row["path"]: row["sha256"] for row in current["authoring"]["files"]}
        if _files(root) != expected:
            raise AuthoringPublicationError("Published native Authoring file set changed")
        doc = native_source.parse_file(root / AUTHOR, workspace=root, identity=receipt["parser"])
        if doc.source_identity != receipt.get("source"):
            raise AuthoringPublicationError("Published native source capture changed")
        integration = integration or ProductionAuthoringIntegration()
        result = integration._validate_authored_selection(current, run_path, _root=root, _document=doc)
        if _safe(root, SELECTION).read_bytes() != result["selection_bytes"]:
            raise AuthoringPublicationError("Published native selection is not its checked canonical content")
        if any(current.get(key) != value for key, value in result["patch"].items()):
            raise AuthoringPublicationError("Published native domain registration changed")
        return {**result, "attempt": current}
    except OSError as exc:
        raise AuthoringPublicationError("Published Authoring evidence is unavailable") from exc
