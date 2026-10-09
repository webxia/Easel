"""Actual installed Hypit static check; no runtime, renderer, Provider or Build."""
import pytest

from easel.integrations.hypit import service, authoring_publication as publication
from easel.integrations.hypit.cli import HypitCLI
from tests.test_material_integration import material_integration_env
from tests.test_native_authoring_publication import native_owner


@pytest.mark.parametrize("material_integration_env", [
    {"hypit_source": "easel-hypit-source@1"},
], indirect=True)
def test_native_publication_with_actual_installed_hypit_static_check(material_integration_env):
    attempt, root = native_owner(material_integration_env)
    ready = service.complete_film_authoring(attempt["attempt_id"], cli=HypitCLI(timeout=60))
    assert ready["authoring_status"] == "AUTHORING_READY"
    check = ready["authoring"]["check"]
    assert check["format"] == "hypit.cli-check@1" and check["sourceKind"] == "run"
    assert check["ok"] is True and check["targets"] == ["final.video"]
    assert check["candidates"] == check["satisfactions"] == 0
    assert "fixture_boundary" not in check
    publication.validate_current(ready, publication.RUN)
