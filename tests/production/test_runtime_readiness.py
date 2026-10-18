"""S6-14: a stale backend must not accept Work writes or a resume."""
import pytest

from easel.production import runtime_readiness as readiness
from easel.production.errors import ProductionError
from easel.production.service import WorkService
from easel.production.store import Store


def test_fresh_code_allows_work_commands(tmp_path):
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    result=service.command('create',{'title':'Fresh worker'},command_id='fresh-create')
    assert result['work_id']
    assert readiness.backend_code_freshness()['reload_required'] is False


def test_stale_code_detected_and_blocks_new_write_before_any_work_mutation(tmp_path,monkeypatch):
    store=Store(tmp_path/'outputs/_production/production.sqlite3')
    store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    monkeypatch.setattr(readiness,'_capture_production_sources',
                        lambda:{'creation.py':(9000,100)})
    monkeypatch.setattr(readiness,'_LOADED_SOURCES',{'creation.py':(8000,100)})
    assert readiness.backend_code_freshness()['reload_required'] is True
    with pytest.raises(ProductionError) as exc:
        service.command('create',{'title':'Must not be created'},command_id='stale-create')
    assert exc.value.code=='backend_reload_required'
    assert exc.value.status_code==503
    with store.connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM works').fetchone()[0]==0


def test_backend_freshness_replay_recovers_after_actual_restart(monkeypatch):
    monkeypatch.setattr(readiness,'_capture_production_sources',
                        lambda:{'creation.py':(9000,100)})
    monkeypatch.setattr(readiness,'_LOADED_SOURCES',{'creation.py':(8000,100)})
    with pytest.raises(ProductionError):
        readiness.require_current_backend()
    # Only process reload should capture the new source map.
    monkeypatch.setattr(readiness,'_LOADED_SOURCES',{'creation.py':(9000,100)})
    readiness.require_current_backend()
    assert readiness.backend_code_freshness()['reload_required'] is False
