"""Prepare an unsent Easel turn using public OpenClaw session RPCs.

No local tokenizer, transcript editing, model retry, or production authority.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from urllib.parse import urlsplit, urlunsplit

from .gateway_questions import GatewayClient, GatewayRPCError
from .production.service import row


class ContextPreparationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class SessionRPC:
    def __init__(self, url, token):
        target = urlsplit(url)
        if target.scheme not in {'http', 'https'} or not target.netloc or target.username or target.password:
            raise ValueError('invalid gateway URL')
        self.client = GatewayClient(url=urlunsplit((
            'wss' if target.scheme == 'https' else 'ws', target.netloc, target.path, '', ''
        )), token=token)

    def describe(self, key):
        response = self.client.rpc('sessions.describe', {
            'key': key, 'agentId': 'main', 'includeDerivedTitles': False, 'includeLastMessage': False,
        })
        if not isinstance(response, dict) or 'session' not in response:
            raise ContextPreparationError('invalid_session_response')
        return response['session']

    def compact(self, key):
        # Omit maxLines: that option truncates history rather than summarizing it.
        return self.client.rpc('sessions.compact', {'key': key, 'agentId': 'main'}, timeout=600)

    def close(self):
        self.client.close()


def pressure(session):
    if not isinstance(session, dict):
        return None
    status = session.get('contextBudgetStatus')
    if not isinstance(status, dict) or status.get('source') != 'pre-prompt-estimate':
        return None
    if (status.get('shouldCompact') is not True or status.get('sessionId') != session.get('sessionId')
        or not status.get('sessionId') or status.get('provider') != session.get('modelProvider')
        or status.get('model') != session.get('model') or session.get('liveModelSwitchPending')
        or not isinstance(status.get('contextTokenBudget'), (float, int))
        or status['contextTokenBudget'] <= 0 or status['contextTokenBudget'] != session.get('contextTokens')):
        return None
    return {k: status[k] for k in ('sessionId', 'provider', 'model', 'updatedAt', 'route',
            'contextTokenBudget', 'estimatedPromptTokens', 'promptBudgetBeforeReserve') if k in status}


def checkpoint(session):
    latest = (session or {}).get('latestCompactionCheckpoint') or {}
    return {'count': (session or {}).get('compactionCheckpointCount'),
            'id': latest.get('checkpointId') if isinstance(latest, dict) else None}


class ContextPreparation:
    def __init__(self, bridge, url, token, *, rpc_factory=None):
        self.bridge, self.store = bridge, bridge.store
        self.url, self.token, self.rpc_factory = url, token, rpc_factory or SessionRPC

    def _read(self, conn, turn_id):
        record = row(conn, 'conversation_turns', turn_id)
        payload = json.loads(record['payload_json'])
        segment = row(conn, 'conversation_segments', record['segment_id'])
        if (segment['revoked_at'] or payload.get('run_id') or record['state'] not in {'reserved', 'dispatching'}
            or payload.get('session_key') != 'agent:main:easel-pipeline:'+segment['id']
            or self.bridge.conversations.segment(conn, segment['ui_session'])['id'] != segment['id']):
            raise ContextPreparationError('turn_not_unsent')
        return record, payload, segment

    def _update(self, turn_id, owner, **values):
        with self.store.transaction() as conn:
            record, payload, _ = self._read(conn, turn_id)
            preparation = payload['context_preparation']
            if preparation.get('owner') != owner or preparation.get('chat_submitted'):
                raise ContextPreparationError('preparation_owned_elsewhere')
            preparation.update(values)
            self.bridge._save(conn, turn_id, payload, record['state'])
            return preparation

    @staticmethod
    def _identity(session, expected):
        if session is None and expected is None:
            return
        if not isinstance(session, dict) or not session.get('sessionId') or (expected and session['sessionId'] != expected):
            raise ContextPreparationError('session_changed')

    def _empty_length_evidence(self, turn_id, segment, session):
        """One known empty reply can justify compacting before a NEW message.

        This is not a token-budget estimate or permission to replay the failed
        turn. A native-ended reply, unchanged model and official checkpoint are
        required; UNKNOWN and partial/tool replies never qualify.
        """
        if (not isinstance(session,dict) or session.get('hasActiveRun')
                or session.get('status') in {'running','queued'} or session.get('liveModelSwitchPending')):
            return None
        with self.store.connection() as conn:
            prior=conn.execute('SELECT * FROM conversation_turns WHERE segment_id=? AND id!=? ORDER BY created_at DESC,id DESC LIMIT 1',
                               (segment['id'],turn_id)).fetchone()
        if not prior or prior['state']!='ended':return None
        payload=json.loads(prior['payload_json']);diagnostic=payload.get('model_diagnostic') or {}
        prep=payload.get('context_preparation') or {}
        if (payload.get('delivery_state')!='interrupted' or not prep.get('chat_submitted')
                or diagnostic.get('stop_reason')!='length' or diagnostic.get('text_chars')!=0
                or diagnostic.get('tool_calls')!=0 or payload.get('answer')
                or not session.get('model') or not session.get('modelProvider')
                or diagnostic.get('model')!=session['model'] or diagnostic.get('provider')!=session['modelProvider']
                or (prep.get('evidence') or {}).get('source')=='known-empty-length'):
            return None
        from datetime import datetime
        failed_at=datetime.fromisoformat(prior['created_at'].replace('Z','+00:00')).timestamp()*1000
        latest=session.get('latestCompactionCheckpoint') or {}
        if isinstance(latest.get('createdAt'),(int,float)) and latest['createdAt']>=failed_at:
            return None
        return {'source':'known-empty-length','source_turn_id':prior['id'],
                'sessionId':session['sessionId'],'provider':session['modelProvider'],
                'model':session['model'],'contextTokenBudget':session.get('contextTokens')}

    def prepare(self, turn_id):
        owner = secrets.token_hex(16)
        with self.store.transaction() as conn:
            record, payload, segment = self._read(conn, turn_id)
            previous = payload.get('context_preparation', {})
            if previous.get('chat_submitted') or previous.get('state') in {'failed', 'cancelled'}:
                raise ContextPreparationError('preparation_stopped')
            if previous.get('owner') and payload.get('delivery_lease_until', 0) > time.time():
                raise ContextPreparationError('preparation_busy')
            preparation = {**previous, 'owner': owner, 'state': previous.get('state', 'checking')}
            payload.update(context_preparation=preparation, delivery_state='streaming', delivery_lease_until=time.time()+30)
            self.bridge._save(conn, turn_id, payload, record['state'])
            key = payload['session_key']
            expected = segment['native_session_id']
        rpc = None
        try:
            rpc = self.rpc_factory(self.url, self.token)
            session = rpc.describe(key)
            self._identity(session, expected)
            prior_state = preparation['state']
            if prior_state in {'compacting', 'unknown'}:
                # A disconnected call is not idempotent. Only a new official
                # checkpoint, same identity and cleared pressure prove progress.
                self._identity(session, preparation.get('session_id'))
                before, after = preparation.get('checkpoint', {}), checkpoint(session)
                progressed = (isinstance(before.get('count'), int) and isinstance(after.get('count'), int)
                              and after['count'] > before['count']) or (after.get('id') and after['id'] != before.get('id'))
                evidence = preparation.get('evidence', {})
                same_selection = (session.get('model') == evidence.get('model')
                                  and session.get('modelProvider') == evidence.get('provider')
                                  and session.get('contextTokens') == evidence.get('contextTokenBudget'))
                if (not progressed or not same_selection or session.get('contextBudgetStatus')
                    or session.get('hasActiveRun') or session.get('status') in {'running','queued'}):
                    raise ContextPreparationError('compaction_unresolved')
                self._update(turn_id, owner, state='compacted', after_checkpoint=after)
            elif prior_state not in {'compacted', 'ready'}:
                evidence = pressure(session) or self._empty_length_evidence(turn_id,segment,session)
                if evidence:
                    self._update(turn_id, owner, state='compacting', evidence=evidence,
                                 session_id=session['sessionId'], checkpoint=checkpoint(session))
                    try:
                        outcome = rpc.compact(key)
                    except GatewayRPCError:
                        self._update(turn_id, owner, state='failed', reason='compaction_rejected')
                        raise ContextPreparationError('compaction_rejected')
                    if not isinstance(outcome, dict):
                        raise ContextPreparationError('compaction_unresolved')
                    if (outcome.get('result') or {}).get('details', {}).get('pending') is True:
                        raise ContextPreparationError('compaction_unresolved')
                    if outcome.get('ok') is not True or outcome.get('compacted') is not True:
                        self._update(turn_id, owner, state='failed', reason='compaction_not_completed')
                        raise ContextPreparationError('compaction_not_completed')
                    tokens = outcome.get('result') or {}
                    before, after = tokens.get('tokensBefore'), tokens.get('tokensAfter')
                    if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after >= before:
                        self._update(turn_id, owner, state='failed', reason='compaction_no_progress')
                        raise ContextPreparationError('compaction_no_progress')
                    session = rpc.describe(key)
                    self._identity(session, preparation.get('session_id') or evidence['sessionId'])
                    self._update(turn_id, owner, state='compacted', after_checkpoint=checkpoint(session),
                                 tokens_before=before, tokens_after=after)
            with self.store.transaction() as conn:
                record, payload, segment = self._read(conn, turn_id)
                prep = payload['context_preparation']
                if prep.get('owner') != owner or prep.get('cancel_requested'):
                    raise ContextPreparationError('preparation_cancelled')
                self._identity(session, segment['native_session_id'])
                prompt = self.bridge.build_prompt(conn, segment, payload)
                payload['prompt_hash'] = hashlib.sha256(prompt.encode()).hexdigest()
                if payload.get('origin') == 'task_result':
                    payload['result_prompt'] = prompt
                payload['visible_proposals'] = [] if payload.get('origin') == 'handoff' else [r[0] for r in conn.execute(
                    "SELECT id FROM conversation_proposals WHERE segment_id=? AND state IN ('proposed','applied')", (segment['id'],))]
                if segment['work_id']:
                    payload['revision'] = row(conn, 'works', segment['work_id'])['revision']
                prep.update(state='ready')
                self.bridge._save(conn, turn_id, payload, record['state'])
                return {'prompt': prompt, 'payload': payload, 'preparation_owner': owner}
        except Exception as exc:
            with self.store.transaction() as conn:
                record = row(conn, 'conversation_turns', turn_id)
                payload = json.loads(record['payload_json'])
                prep = payload.get('context_preparation', {})
                if prep.get('owner') == owner and not prep.get('chat_submitted'):
                    if prep.get('state') in {'compacting', 'unknown'}:
                        prep.update(state='unknown', reason='compaction_unresolved')
                    elif prep.get('state') not in {'failed', 'cancelled'}:
                        prep.update(state='failed', reason=getattr(exc, 'code', 'context_unavailable'))
                    cancelled = prep.get('cancel_requested') and prep['state'] != 'unknown'
                    if cancelled:
                        prep['state'] = 'cancelled'
                    payload.update(delivery_state='interrupted', delivery_lease_until=time.time()+30)
                    self.bridge._save(conn, turn_id, payload, 'ended' if cancelled else record['state'])
            raise ContextPreparationError(getattr(exc, 'code', 'context_unavailable')) from None
        finally:
            if rpc:
                rpc.close()

    def submitted(self, turn_id, owner):
        """Durable admission immediately before POST, never repeated on replay."""
        with self.store.transaction() as conn:
            record, payload, _ = self._read(conn, turn_id)
            prep = payload.get('context_preparation', {})
            if prep.get('owner') != owner or prep.get('state') != 'ready' or prep.get('chat_submitted') or prep.get('cancel_requested'):
                raise ContextPreparationError('turn_not_unsent')
            prep['chat_submitted'] = True
            payload.update(delivery_state='streaming', delivery_lease_until=time.time()+30)
            self.bridge._save(conn, turn_id, payload, 'dispatching')

    def cancel(self, turn_id):
        with self.store.transaction() as conn:
            record = row(conn, 'conversation_turns', turn_id)
            payload = json.loads(record['payload_json'])
            prep = payload.get('context_preparation')
            if not prep or prep.get('chat_submitted') or payload.get('run_id'):
                return False
            prep['cancel_requested'] = True
            # A compact call may still finish after the local wait is cancelled.
            pending = prep.get('state') in {'compacting', 'unknown'}
            if not pending:
                prep['state'] = 'cancelled'
            payload.update(delivery_state='interrupted', delivery_lease_until=time.time()+30 if pending else 0)
            self.bridge._save(conn, turn_id, payload, record['state'] if pending else 'ended')
            return True

    @staticmethod
    def recoverable(bridge, *, turn_id=None):
        """Reuse the result-relay tick for unfinished preparation, not chat retry."""
        with bridge.store.connection() as conn:
            for record in conn.execute("SELECT t.*,s.ui_session,s.revoked_at FROM conversation_turns t JOIN conversation_segments s ON s.id=t.segment_id WHERE t.state IN ('reserved','dispatching') ORDER BY t.created_at,t.id"):
                if turn_id is not None and record['id'] != turn_id:
                    continue
                payload = json.loads(record['payload_json'])
                prep = payload.get('context_preparation', {})
                if (record['revoked_at'] or payload.get('run_id') or prep.get('chat_submitted')
                    or prep.get('state') not in {'checking','compacting','unknown','compacted','ready'}
                    or payload.get('delivery_lease_until',0) > time.time()):
                    continue
                return {'turn_id':record['id'], 'ui_session':record['ui_session'], 'payload':payload}
        return None
