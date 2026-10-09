"""Native publication through the real Planning / Gate / Authoring owners.

Only the Hypit CLI check boundary is replaced. The installed parser, material
evidence, candidate derivation, file promotion and Attempt persistence are real.
"""
import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from easel.integrations.hypit import service
from easel.integrations.hypit import authoring_publication as publication
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit.native_source import parse_file, parse_run
from easel.integrations.material_layer import (
    MaterialGateIntegration, PlanningIntegration, ProductionAuthoringIntegration,
)
from easel.materials.application.assembly import MaterialBundleAssembler
from easel.materials.application.readiness import MaterialReadinessCalculator
from easel.materials.store import AttemptMaterialStore
from tests.test_material_integration import (
    material_integration_env, _planning, _contracts, _record_authored_selection,
)

pytestmark = pytest.mark.parametrize("material_integration_env", [
    {"hypit_source": "easel-hypit-source@1"},
], indirect=True)


def native_owner(attempt):
    _planning(attempt)
    root = Path(attempt["workspace"]["path"])
    plan, asset, supply, bundle, _, _ = _contracts(attempt, root)
    stream = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(stream, format="PNG")
    data = stream.getvalue()
    store = AttemptMaterialStore(root)
    store.resolve_asset_locator(asset.file.path).write_bytes(data)
    asset = asset.model_copy(update={"file": asset.file.model_copy(update={
        "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
    })})
    store.write_asset(asset)
    bundle = MaterialBundleAssembler().assemble(plan, supply, (asset,), bundle.matches, bundle_id=bundle.bundle_id)
    readiness, gaps = MaterialReadinessCalculator(store=store).calculate(plan, bundle)
    attempt.update(MaterialGateIntegration().record(attempt, plan, bundle, supply, readiness, gaps)["attempt"])
    attempt.update(ProductionAuthoringIntegration().prepare(attempt)["attempt"])
    attempt.update(service.begin_film_authoring(attempt["attempt_id"]))
    _record_authored_selection(attempt, asset, root)
    selection = json.loads((root / publication.SELECTION).read_bytes())
    src = selection["assets"][0]["src"]
    source = f'''<?svml using="@hypit/markup@1"?>
<svml>
<import as="time" from="@hypit/timeline-author@1"/>
<import as="media" from="@hypit/media@1"/>
<import as="picture" from="@hypit/media-track@1"/>
<import as="space" from="@hypit/spatial@1"/>
<import as="film" from="@hypit/film@1"/>
<import as="render" from="@hypit/render-hyperframes@1"/>
<import as="recipes" source="./recipes.svs"/>
<time:Clock id="clock" frame-rate="24"/>
<time:Timeline id="program" clock={{clock}} end="1s"/>
<space:Canvas id="canvas" width="1080" height="1920"/>
<space:Frame id="full-frame" within={{canvas}} left="0px" top="0px" right="1080px" bottom="1920px"/>
<space:Extent id="image-size" width="1" height="1"/>
<media:Image id="selected" src="{src}"/>
<picture:Track id="pictures" canvas={{canvas}} timeline={{program.timeline}}>
  <Item id="scene-main" image={{selected}} extent={{image-size}} frame={{full-frame}} appearance={{recipes.media.frame}} at="0s" for="1s"/>
</picture:Track>
<film:Film id="movie" canvas={{canvas}} timeline={{program.timeline}} appearance={{recipes.film.memo}}>
  <Track source={{pictures.visual}}/>
</film:Film>
<render:Video id="final" composition={{movie.composition}} timeline={{program.timeline}}/>
</svml>
<!-- 原始模型产物 😀 -->
'''
    source += "<!-- Easel expression: " + json.dumps({
        "need_id": "need-main", "element_ids": ["scene-main"], "at_seconds": 0,
        "end_seconds": 1, "responsibility": "material",
    }, ensure_ascii=False) + " -->\n"
    (root / publication.AUTHOR).write_bytes(source.replace("\n", "\r\n").encode())
    (root / publication.AUTHOR).with_name("recipes.svs").write_text(
        '<?svml using="@hypit/svs@1"?>\n<sheet version="1">\n'
        'film.memo { background: #101820; }\nmedia.frame { stack-order: 0; }\n</sheet>\n')
    return service.get_film_attempt(attempt["attempt_id"]), root


class CheckBoundary:
    def __init__(self, root, *, ok=True, effect=None):
        self.root, self.ok, self.effect = root, ok, effect
        self.before = publication._files(root)
        self.calls = []

    def check(self, workspace, source):
        assert workspace != self.root
        assert workspace.is_relative_to(self.root / ".easel/native-authoring")
        assert publication._files(self.root) == self.before
        assert source == workspace / publication.RUN
        self.calls.append(workspace)
        # Real installed grammar, with no renderer/provider execution.
        parse_file(workspace / publication.AUTHOR, workspace=workspace)
        _, run, _ = parse_run(source, workspace=workspace)
        assert run["targets"] == [{"output": "final.video"}]
        if self.effect:
            self.effect(workspace)
        if not self.ok:
            from easel.integrations.hypit.errors import HypitCLIError
            raise HypitCLIError("Hypit Authoring 静态校验未通过", returncode=1, payload={
                "format": "hypit.cli-error@1", "ok": False,
                "error": {"code": "AUTHOR_INPUT_TYPE_MISMATCH", "message": "fixture type mismatch"}})
        return {"format": "hypit.cli-check@1", "ok": True, "sourceKind": "run",
                "run": publication.RUN, "author": publication.AUTHOR, "frontend": "@hypit/run-markup@1",
                "targetCount": 1, "targets": ["final.video"], "candidates": 0, "satisfactions": 0,
                "historicalOutputCount": 0, "fixture_boundary": "HypitCLI.check"}


def test_native_authoring_owner_publishes_one_checked_candidate_and_replays_read_only(material_integration_env):
    attempt, root = native_owner(material_integration_env)
    original = {name: (root / name).read_bytes() for name in publication.TARGETS if (root / name).exists()}
    cli = CheckBoundary(root)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY"
    assert ready["production_authoring"]["status"] == "READY"
    assert not ready.get("pending_authoring_publication") and not ready.get("native_authoring_validation")
    assert len(cli.calls) == 1
    receipt = ready["authoring"]["native_publication"]
    directory = root / ".easel/native-authoring" / receipt["publication_id"] / "originals"
    assert all((directory / name).read_bytes() == raw for name, raw in original.items())
    assert (root / publication.AUTHOR).read_bytes() == original[publication.AUTHOR]
    assert (root / publication.SIDECAR).read_bytes() == original[publication.RUN]
    frozen = publication._files(root)
    validated = ProductionAuthoringIntegration().validate_authored_selection(ready, publication.RUN)
    assert validated["attempt"] == ready and publication._files(root) == frozen
    assert service.complete_film_authoring(attempt["attempt_id"], cli=cli) == ready
    assert len(cli.calls) == 1
    assert sum(row.get("event") == "authoring_ready" for row in ready["history"]) == 1



def test_native_authoring_actual_installed_hypit_static_check_without_build(material_integration_env):
    """The installed local Hypit checker, not only our Python AST, admits the frozen candidate."""
    from easel.integrations.hypit.cli import HypitCLI
    attempt, root = native_owner(material_integration_env)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=HypitCLI(timeout=60))
    assert ready["authoring_status"] == "AUTHORING_READY"
    assert ready["runtime_status"] == "NOT_CONFIGURED"
    assert ready["execution_status"] == "BLOCKED"
    assert ready["authoring"]["check"]["ok"] is True
    assert ready["authoring"]["native_publication"]["schema"] == publication.SCHEMA
    assert not ready.get("pending_authoring_publication")

@pytest.mark.parametrize("cut", ["first_target", "last_target"])
def test_native_authoring_recovers_durable_prefix_without_rechecking_or_agent(
        material_integration_env, monkeypatch, cut):
    attempt, root = native_owner(material_integration_env)
    cli = CheckBoundary(root)
    publish = publication._publish_file
    seen = []

    def interrupted(workspace, row, raw):
        publish(workspace, row, raw)
        seen.append(row["path"])
        if cut == "first_target" or row["path"] == publication.SELECTION:
            raise OSError("fixture interruption after durable replacement")

    monkeypatch.setattr(publication, "_publish_file", interrupted)
    with pytest.raises(publication.AuthoringPublicationError, match="storage failed"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert pending["authoring_status"] == "AUTHORING_RUNNING"
    intent = pending["pending_authoring_publication"]
    assert intent["targets"] and len(cli.calls) == 1
    with pytest.raises(publication.AuthoringPublicationError, match="incomplete"):
        service.authoring_agent_task(attempt["attempt_id"])
    with pytest.raises(publication.AuthoringPublicationError, match="incomplete"):
        ProductionAuthoringIntegration().validate_authored_selection(pending, publication.RUN)
    monkeypatch.setattr(publication, "_publish_file", publish)
    import asyncio
    from web import app as web
    monkeypatch.setattr(service, "_cli", lambda supplied=None: cli)
    def no_agent(*args, **kwargs):
        raise AssertionError("pending publication must not redispatch an Agent")
    monkeypatch.setattr(web, "_authoring_agent_message", no_agent)
    restored = asyncio.run(web._run_film_authoring(attempt["attempt_id"]))
    assert restored["authoring_status"] == "AUTHORING_READY"
    assert restored["authoring"]["native_publication"]["publication_id"] == intent["publication_id"]
    assert len(cli.calls) == 1
    assert publication._files(root) == intent["after_files"]
    assert sum(row.get("event") == "authoring_ready" for row in restored["history"]) == 1


def test_native_authoring_failed_check_keeps_raw_files_and_requires_content_repair(material_integration_env):
    attempt, root = native_owner(material_integration_env)
    cli = CheckBoundary(root, ok=False)
    with pytest.raises(HypitIntegrationError, match="静态校验"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    failed = service.get_film_attempt(attempt["attempt_id"])
    assert failed["authoring_status"] == "AUTHORING_FAILED"
    assert not failed.get("pending_authoring_publication") and not failed.get("native_authoring_validation")
    assert publication._files(root) == cli.before
    assert len(cli.calls) == 1


def test_native_authoring_local_check_io_recovers_saved_input_without_model(material_integration_env):
    attempt, root = native_owner(material_integration_env)
    def fail(workspace):
        raise OSError("fixture local check pipe failed")
    cli = CheckBoundary(root, effect=fail)
    with pytest.raises(publication.AuthoringPublicationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert pending["authoring_status"] == "AUTHORING_RUNNING"
    assert pending["native_authoring_validation"]["input_files"] == cli.before
    assert not pending.get("pending_authoring_publication")
    assert publication._files(root) == cli.before
    cli.effect = None
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY" and len(cli.calls) == 2

@pytest.mark.parametrize("drift", ["target", "dependency", "added", "removed", "candidate"])
def test_native_authoring_pending_rejects_other_writer_without_overwrite(
        material_integration_env, monkeypatch, drift):
    attempt, root = native_owner(material_integration_env)
    cli = CheckBoundary(root)
    publish = publication._publish_file
    def interrupt(workspace, row, raw):
        publish(workspace, row, raw)
        raise OSError("fixture stops the prefix")
    monkeypatch.setattr(publication, "_publish_file", interrupt)
    with pytest.raises(publication.AuthoringPublicationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    intent = pending["pending_authoring_publication"]
    monkeypatch.setattr(publication, "_publish_file", publish)
    if drift == "target":
        changed = root / publication.RUN
    elif drift == "candidate":
        changed = root / intent["staging"] / publication.AUTHOR
    elif drift == "added":
        changed = root / "unexpected-dependency.json"
    else:
        changed = (root / publication.AUTHOR).with_name("recipes.svs")
    raw = changed.read_bytes() if changed.exists() else None
    if drift == "removed":
        changed.unlink()
    else:
        changed.write_bytes(b"fixture third writer bytes")
    before_retry = publication._files(root)
    with pytest.raises(publication.AuthoringPublicationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert publication._files(root) == before_retry
    assert service.get_film_attempt(attempt["attempt_id"])["pending_authoring_publication"] == intent
    assert len(cli.calls) == 1
    if raw is None:
        changed.unlink()
    else:
        changed.write_bytes(raw)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY" and len(cli.calls) == 1


def test_native_authoring_detects_dependency_change_during_check(material_integration_env):
    attempt, root = native_owner(material_integration_env)
    changed = root / "new-dependency.json"
    cli = CheckBoundary(root, effect=lambda workspace: changed.write_bytes(b"{}"))
    with pytest.raises(publication.AuthoringPublicationError, match="input changed"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert pending["authoring_status"] == "AUTHORING_RUNNING"
    assert not pending.get("pending_authoring_publication")
    assert not (root / publication.SIDECAR).exists()
    with pytest.raises(publication.AuthoringPublicationError, match="model Authoring files changed"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert len(cli.calls) == 1 and changed.read_bytes() == b"{}"


def test_native_authoring_concurrent_completes_share_one_candidate(material_integration_env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    attempt, root = native_owner(material_integration_env)
    cli, barrier = CheckBoundary(root), Barrier(2)
    def finish():
        barrier.wait(timeout=15)
        return service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(finish), executor.submit(finish)
        results = [first.result(timeout=45), second.result(timeout=45)]
    assert results[0]["authoring"] == results[1]["authoring"]
    assert len(cli.calls) == 1
    assert sum(row.get("event") == "authoring_ready" for row in results[-1]["history"]) == 1


def test_native_selection_read_io_stays_local_and_preserves_authoring_state(
        material_integration_env, monkeypatch):
    from easel.integrations.output_receipts import OutputReceiptError
    attempt, root = native_owner(material_integration_env)
    cli = CheckBoundary(root)
    read_bytes = Path.read_bytes
    validate = ProductionAuthoringIntegration._validate_authored_selection
    inside = False
    def fail_read(path):
        if inside and path.name == "material-selection.json":
            raise OSError("fixture selection receipt read failure")
        return read_bytes(path)
    def validate_with_io(self, *args, **kwargs):
        nonlocal inside
        inside = True
        try:
            return validate(self, *args, **kwargs)
        finally:
            inside = False
    monkeypatch.setattr(Path, "read_bytes", fail_read)
    monkeypatch.setattr(ProductionAuthoringIntegration, "_validate_authored_selection", validate_with_io)
    with pytest.raises(OutputReceiptError, match="selection storage"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert pending["authoring_status"] == "AUTHORING_RUNNING"
    assert pending["native_authoring_validation"]["input_files"] == cli.before
    assert not cli.calls and publication._files(root) == cli.before
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(ProductionAuthoringIntegration, "_validate_authored_selection", validate)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring_status"] == "AUTHORING_READY" and len(cli.calls) == 1

def test_native_authoring_partial_publication_cold_process_recovery(material_integration_env, monkeypatch):
    """Restarted Python must consume the persisted intent, never recheck or invoke an Agent."""
    import os
    import subprocess
    import sys
    attempt, root = native_owner(material_integration_env)
    cli = CheckBoundary(root)
    original_publish = publication._publish_file
    def interrupt_after_first_owned_write(workspace, target, raw):
        original_publish(workspace, target, raw)
        raise OSError("fixture process interruption after one persisted target")
    monkeypatch.setattr(publication, "_publish_file", interrupt_after_first_owned_write)
    with pytest.raises(publication.AuthoringPublicationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    intent = pending["pending_authoring_publication"]
    assert len(cli.calls) == 1
    assert pending["authoring_status"] == "AUTHORING_RUNNING"
    monkeypatch.setattr(publication, "_publish_file", original_publish)
    base = Path(os.environ["EASEL_HYPIT_HOME"]).parents[1]
    code = """import os, sys, socket
from pathlib import Path
from easel import creation, creative_mode
from easel.integrations.hypit import handoff, service, authoring_publication as publication
from easel.runtime_config import EaselRuntimeConfig
base = Path(sys.argv[1])
creation.OUTPUTS_DIR = base / "outputs"
creation.CREATIONS_DIR = base / "outputs" / "_creations"
creative_mode.CREATIVE_MODES_DIR = base / "creative_modes"
handoff.CREATIVE_MODES_DIR = base / "creative_modes"
original_config = EaselRuntimeConfig.load
EaselRuntimeConfig.load = classmethod(lambda cls: original_config(
    environ={"EASEL_MATERIAL_LIBRARY_ROOT": str(base / "material-library")},
    env_file=base / "absent.env"))
socket.socket.connect = lambda *args, **kwargs: (_ for _ in ()).throw(
    AssertionError("cold Authoring recovery must not access the network"))
class NoRecheck:
    def check(self, *args, **kwargs):
        raise AssertionError("already checked candidate may not invoke Hypit CLI")
attempt = service.complete_film_authoring(sys.argv[2], cli=NoRecheck())
assert attempt["authoring_status"] == "AUTHORING_READY"
assert attempt["authoring"]["native_publication"]["publication_id"] == sys.argv[3]
assert attempt.get("pending_authoring_publication") is None
assert sum(row.get("event") == "authoring_ready" for row in attempt["history"]) == 1
print("NATIVE_AUTHORING_COLD_RECOVERY_PASS")
"""
    child_env = os.environ.copy()
    child_env["EASEL_MATERIAL_LIBRARY_ROOT"] = str(base / "material-library")
    child = subprocess.run([sys.executable, "-c", code, str(base),
                            attempt["attempt_id"], intent["publication_id"]],
                           capture_output=True, text=True, env=child_env, timeout=75)
    assert child.returncode == 0, child.stderr
    assert "NATIVE_AUTHORING_COLD_RECOVERY_PASS" in child.stdout
    restored = service.get_film_attempt(attempt["attempt_id"])
    assert restored["authoring"]["native_publication"]["publication_id"] == intent["publication_id"]
    assert publication._files(root) == intent["after_files"]
    assert len(cli.calls) == 1


def test_native_authoring_final_creation_cas_rechecks_dependencies(material_integration_env, monkeypatch):
    attempt, root = native_owner(material_integration_env)
    cli = CheckBoundary(root)
    save = service._save_attempt
    late_dependency = root / "changed-while-waiting-for-creation-lock.json"
    injected = False
    def delayed_save(attempt_id, mutate):
        def under_creation_lock(item):
            nonlocal injected
            if mutate.__name__ == "finish" and item.get("pending_authoring_publication") and not injected:
                injected = True
                late_dependency.write_bytes(b"fixture concurrent writer")
            return mutate(item)
        return save(attempt_id, under_creation_lock)
    monkeypatch.setattr(service, "_save_attempt", delayed_save)
    with pytest.raises(publication.AuthoringPublicationError, match="final registration"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    pending = service.get_film_attempt(attempt["attempt_id"])
    assert injected and pending["authoring_status"] == "AUTHORING_RUNNING"
    intent = pending["pending_authoring_publication"]
    assert len(cli.calls) == 1 and late_dependency.read_bytes() == b"fixture concurrent writer"
    assert not any(row.get("event") == "authoring_ready" for row in pending["history"])
    monkeypatch.setattr(service, "_save_attempt", save)
    late_dependency.unlink()
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert ready["authoring"]["native_publication"]["publication_id"] == intent["publication_id"]
    assert len(cli.calls) == 1


