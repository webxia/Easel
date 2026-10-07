"""Structured Planning capture in the existing request/checkpoint journal.

The Gateway retains the original terminal reply before any local artifact
write. Persistence recovery never grants another model submission.
"""
from __future__ import annotations

import hashlib
import json
import time
from easel.creation_delivery import DeliveryExecutionUncertain
from easel.integrations.openclaw_delivery import PlanningResultError
from easel.integrations.hypit.secrets import SecretRedactor

MAX_REPLY_UTF16 = 3000
MAX_INPUT_BYTES = 64 * 1024


def capture(calls, key, message, session, dispatch, save):
    identity = hashlib.sha256(message.encode()).hexdigest()
    if len(message.encode()) > MAX_INPUT_BYTES:
        raise PlanningResultError('CONTRACT_REJECTED')
    record = calls.get(key)
    if record is not None and (record['request_sha256'] != identity or record['session'] != session):
        raise ValueError('Planning capture request identity changed')
    if record is None:
        record = {'request_sha256': identity, 'session': session, 'input_bytes': len(message.encode()),
                  'result': 'REQUESTED'}
        calls[key] = record
        save()
    if record.get('reply') is None and record['result'] in {
            'MODEL_TRUNCATED', 'MODEL_NO_RESULT', 'STRUCTURED_OUTPUT_INVALID', 'CONTRACT_REJECTED'}:
        raise PlanningResultError(record['result'])
    if record.get('reply') is None:
        started = time.monotonic()
        try:
            reply = dispatch(key, message, session)
        except PlanningResultError as exc:
            record['result'] = exc.result
            save()
            raise
        except DeliveryExecutionUncertain:
            record['result'] = 'TRANSPORT_FAILED'
            save()
            raise
        if not isinstance(reply, str) or not reply.strip():
            record['result'] = 'MODEL_NO_RESULT'
            save()
            raise PlanningResultError(record['result'])
        if len(reply.encode('utf-16-le')) // 2 > MAX_REPLY_UTF16 or reply.rstrip().endswith('…'):
            record['result'] = 'MODEL_TRUNCATED'
            save()
            raise PlanningResultError(record['result'])
        if SecretRedactor.contains_secret(reply):
            record['result'] = 'STRUCTURED_OUTPUT_INVALID'
            save()
            raise PlanningResultError(record['result'])
        record.update(reply=reply, reply_sha256=hashlib.sha256(reply.encode()).hexdigest(),
                      output_bytes=len(reply.encode()), elapsed_seconds=time.monotonic()-started,
                      result='MODEL_COMPLETED')
        save()  # Durable capture precedes parsing and all formal file writes.
    if hashlib.sha256(record['reply'].encode()).hexdigest() != record['reply_sha256']:
        raise ValueError('Planning captured result changed')
    try:
        value = json.loads(record['reply'])
        if not isinstance(value, dict):
            raise ValueError('Structured result must be an object')
    except (ValueError, UnicodeError):
        record['result'] = 'STRUCTURED_OUTPUT_INVALID'
        save()
        raise PlanningResultError(record['result'])
    return value


def persist_captured(calls, key, writer, save):
    record = calls[key]
    if record.get('reply') is None:
        raise PlanningResultError('MODEL_NO_RESULT')
    try:
        writer(record['reply'].encode())
    except OSError:
        record['result'] = 'PERSIST_FAILED'
        save()
        raise
    record['result'] = 'ACCEPTED'
    save()
