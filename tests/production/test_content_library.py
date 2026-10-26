"""Library reads preserve accepted versions and never mutate production/publication state."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.production_api import create_router, production_error_handler
from web.publication_api import create_publication_router
from easel.production.errors import ProductionError
from tests.production.test_revision_acceptance import prepared
from tests.production.test_publication import publication


def client_for(service, adapter=None):
    app = FastAPI()
    app.add_exception_handler(ProductionError, production_error_handler)
    app.include_router(create_router(lambda: service))
    if adapter is not None:
        app.include_router(create_publication_router(lambda: service, lambda: adapter))
    return TestClient(app)


def database_state(service):
    with service.store.connection() as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {t: sorted((tuple(r) for r in conn.execute(f'SELECT * FROM "{t}"')), key=repr) for t in tables}


def test_accepted_summary_stays_on_a_and_detects_newer_preview(prepared):
    service, work = prepared
    service.command('accept', {'output_id': 'passed'}, command_id='accept', work_id=work, expected_revision=3)
    before = database_state(service)
    client = client_for(service)
    rows = client.get('/api/production/library').json()
    assert len(rows) == 1
    item = rows[0]
    assert item['work_id'] == work and item['artifact_id'] == 'passed'
    assert item['output_revision'] == 1 and item['accepted_output_id'] == 'passed'
    assert item['latest_artifact_id'] == 'unchecked' and item['latest_output_revision'] == 2
    assert item['has_newer_preview'] is True and item['updated_at']
    assert client.get('/api/production/library?scope=unaccepted').json() == []
    detail = client.get(f'/api/production/works/{work}').json()
    assert detail['accepted_output_id'] == 'passed' and len(detail['artifacts']) == 2
    assert client.get('/api/production/artifacts/passed/content').content == b'fixture-output'
    assert database_state(service) == before


def test_draft_and_preview_list_excludes_deleted_and_hidden_outputs(prepared):
    service, work = prepared
    draft = service.command('create', {'title': 'No output'}, command_id='draft')['work_id']
    client = client_for(service)
    items = {r['work_id']: r for r in client.get('/api/production/library?scope=unaccepted').json()}
    assert items[work]['artifact_id'] == 'unchecked'
    assert items[draft]['artifact_id'] is None and items[draft]['output_revision'] is None
    with service.store.transaction() as conn:
        conn.execute("UPDATE artifacts SET displayable=0 WHERE id='unchecked'")
    assert next(r for r in client.get('/api/production/library?scope=unaccepted').json() if r['work_id'] == work)['artifact_id'] == 'passed'
    with service.store.transaction() as conn:
        conn.execute("UPDATE artifacts SET deleted_at='now' WHERE id='passed'")
        conn.execute("UPDATE works SET deleted_at='now' WHERE id=?", (draft,))
    rows = client.get('/api/production/library?scope=unaccepted').json()
    assert len(rows) == 1 and rows[0]['artifact_id'] is None
    assert client.get('/api/production/library?scope=invalid').status_code == 422


def test_hidden_latest_cannot_create_new_preview_badge(prepared):
    service, work = prepared
    service.command('accept', {'output_id': 'passed'}, command_id='accept', work_id=work, expected_revision=3)
    with service.store.transaction() as conn:
        conn.execute("UPDATE artifacts SET displayable=0 WHERE id='unchecked'")
    item = client_for(service).get('/api/production/library').json()[0]
    assert item['latest_artifact_id'] == 'passed' and item['has_newer_preview'] is False


def test_reading_existing_publication_and_versions_does_not_prepare_or_submit(publication):
    pub, adapter, draft = publication
    client = client_for(pub.service, adapter)
    before = database_state(pub.service)
    for _ in range(2):
        client.get('/api/production/library').raise_for_status()
        client.get(f'/api/production/works/{draft["work_id"]}').raise_for_status()
        rows = client.get(f'/api/production/publications?work_id={draft["work_id"]}').json()
        assert [r['id'] for r in rows] == [draft['id']]
        assert rows[0]['output_id'] == 'passed'
    assert adapter.calls == 0 and database_state(pub.service) == before
