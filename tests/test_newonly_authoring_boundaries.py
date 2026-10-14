"""Contract regressions replacing removed regex/SVRun-only writer tests.

Tests use the real native parser, Gate, staged Publisher, and frozen file
identity. Only Hypit CLI.check is a deterministic in-memory boundary.
"""
from __future__ import annotations

import json
import copy

import pytest

from easel.integrations import result_protocols
from easel.integrations.hypit import authoring_publication as native
from easel.integrations.hypit import service
from easel.integrations.hypit.errors import HypitIntegrationError
from tests.test_material_integration import material_integration_env
from tests.test_native_authoring_publication import native_owner, CheckBoundary

pytestmark = pytest.mark.parametrize(
    "material_integration_env", [{"hypit_source": "easel-hypit-source@1"}],
    indirect=True,
)


@pytest.mark.parametrize('invalid', ['legacy_proposal', 'revoked_confirmation'])
def test_active_export_and_cancel_reject_noncurrent_commission_before_effects(
        material_integration_env, invalid):
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    with creation.edit_creation(attempt['creation_id']) as work:
        row = next(x for x in work['hypit_attempts'] if x['attempt_id'] == attempt['attempt_id'])
        row['execution_status'] = 'BUILD_COMPLETE'
        row['build']['build_id'] = 'offline-existing-build'
        if invalid == 'legacy_proposal':
            work['chat_workflow']['video_plan']['schema'] = 'easel-video-proposal@3'
        else:
            work['chat_workflow']['proposal_status'] = 'DISCUSSING'
    assert result_protocols.inherited(service.get_film_attempt(attempt['attempt_id'])) == result_protocols.current()

    class Boundary:
        calls = []
        def get(self, *args, **kwargs):
            self.calls.append('get')
            raise AssertionError('invalid commission reached get')
        def cancel(self, *args, **kwargs):
            self.calls.append('cancel')
            raise AssertionError('invalid commission reached cancel')
    cli = Boundary()
    for operation in ('export', 'cancel'):
        if operation == 'cancel':
            with creation.edit_creation(attempt['creation_id']) as work:
                next(x for x in work['hypit_attempts'] if x['attempt_id'] == attempt['attempt_id'])['execution_status'] = 'RUNNING'
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        record = copy.deepcopy(creation.get_creation(attempt['creation_id']))
        with pytest.raises(HypitIntegrationError, match='委托|只读'):
            if operation == 'export':
                service.export_film_output(attempt['attempt_id'], 'final.video', cli=cli)
            else:
                service.cancel_film_build(attempt['attempt_id'], cli=cli)
        assert cli.calls == []
        assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        assert creation.get_creation(attempt['creation_id']) == record


@pytest.mark.parametrize("tamper", [
    "unadmitted_source", "unapproved_generator_import", "asset_digest", "forged_need_ids",
    "foreign_run_attempt", "missing_run_identity", "selection_extra_field",
])
def test_unadmitted_native_material_or_run_identity_never_reaches_check(
        material_integration_env, tamper):
    attempt, root = native_owner(material_integration_env)
    assert result_protocols.inherited(attempt) == result_protocols.current()
    author = root / native.AUTHOR
    run = root / native.RUN
    selection = root / native.SELECTION

    if tamper == "unadmitted_source":
        manifest = json.loads(selection.read_text())
        src = manifest["assets"][0]["src"]
        author.write_text(author.read_text().replace(src, "../../../../unadmitted.png"))
    elif tamper == "unapproved_generator_import":
        # Replaces a deleted legacy regex assertion with a current typed
        # Authoring/Material Gate rejection: an unapproved provider cannot
        # enter the native production graph, even with legitimate stock input.
        before_source = author.read_text()
        import_line = '<import as="media" from="@hypit/media@1"/>'
        assert import_line in before_source
        author.write_text(before_source.replace(import_line,
            import_line + '\n<import as="paid_image" from="@hypit/gpt-image@1"/>'))
    elif tamper in {"asset_digest", "forged_need_ids", "selection_extra_field"}:
        manifest = json.loads(selection.read_text())
        if tamper == "asset_digest":
            manifest["assets"][0]["sha256"] = "0" * 64
        elif tamper == "forged_need_ids":
            manifest["assets"][0]["qualified_need_ids"] = ["another-need"]
        else:
            manifest["operator_note"] = "forged admission"
        selection.write_text(json.dumps(manifest, ensure_ascii=False))
    elif tamper == "foreign_run_attempt":
        data = json.loads(run.read_text())
        data["attempt_id"] = "fa_" + "0" * 32
        run.write_text(json.dumps(data, ensure_ascii=False))
    elif tamper == "missing_run_identity":
        run.write_text('<?svml using="@hypit/run-markup@1"?>\\n<svrun version="1"/>\\n')
    before = native._files(root)
    cli = CheckBoundary(root)
    with pytest.raises(HypitIntegrationError):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert not cli.calls
    assert native._files(root) == before  # No model source rewrite or promotion.
    observed = service.get_film_attempt(attempt["attempt_id"])
    assert observed["authoring_status"] != "AUTHORING_READY"


def test_old_protocol_attempt_cannot_enter_native_owner_or_check(material_integration_env):
    from easel import creation
    from easel.integrations.output_receipts import OutputReceiptError
    attempt, root = native_owner(material_integration_env)
    with creation.edit_creation(attempt["creation_id"]) as doc:
        row = next(x for x in doc["hypit_attempts"] if x["attempt_id"] == attempt["attempt_id"])
        row["result_protocols"] = {
            "schema": result_protocols.SCHEMA, "profiles": {},
        }
    before = native._files(root)
    cli = CheckBoundary(root)
    with pytest.raises(OutputReceiptError, match="read-only"):
        service.complete_film_authoring(attempt["attempt_id"], cli=cli)
    assert native._files(root) == before
    assert not cli.calls


def test_current_stopped_commission_can_cancel_existing_build_but_cannot_export(material_integration_env):
    from easel import creation
    attempt, root = native_owner(material_integration_env)
    with creation.edit_creation(attempt['creation_id']) as work:
        work['delivery']['stopped'] = True
        row = next(x for x in work['hypit_attempts'] if x['attempt_id'] == attempt['attempt_id'])
        row['execution_status'] = 'RUNNING'
        row['build']['build_id'] = 'offline-existing-build'
    class Boundary:
        calls = []
        def cancel(self, workspace, build_id):
            assert workspace == root and build_id == 'offline-existing-build'
            self.calls.append(build_id)
            return {'requested': True}
    cli = Boundary()
    result = service.cancel_film_build(attempt['attempt_id'], cli=cli)
    assert result['execution_status'] == 'CANCEL_REQUESTED'
    assert cli.calls == ['offline-existing-build']
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(HypitIntegrationError, match='委托'):
        service.export_film_output(attempt['attempt_id'], 'final.video', cli=cli)
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
