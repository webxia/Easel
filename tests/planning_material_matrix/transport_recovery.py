"""Versioned transport evidence for the existing isolated text-evaluation proxy.

No Provider schema, billing assumptions, credential output or production retries.
Only an observed failure before the first application HTTP write is retryable.
A CONNECT tunnel is connection setup, not a model POST. TLS verification and
normal urllib proxy selection remain unchanged. Old manifests do not opt in.
"""
from __future__ import annotations

from dataclasses import dataclass
import errno
import http.client
import socket
import ssl
import time
import urllib.error
import urllib.request

POLICY = 'phase-aware-text-transport@1'


@dataclass
class Progress:
    phase: str = 'PREPARING'
    connection_observed: bool = False
    request_write_attempted: bool = False
    response_headers: bool = False
    response_complete: bool = False

    def evidence(self):
        return {'policy': POLICY, 'phase': self.phase,
                'connection_observed': self.connection_observed,
                'request_write_attempted': self.request_write_attempted,
                'response_headers': self.response_headers,
                'response_complete': self.response_complete}


def failure_evidence(error, progress):
    """Closed categories only: exception messages/URLs/headers are never saved."""
    cause = error
    for _ in range(4):
        if isinstance(cause, urllib.error.URLError) and isinstance(cause.reason, BaseException):
            cause = cause.reason
        else:
            break
    if isinstance(cause, ssl.SSLCertVerificationError):
        category = 'TLS_CERTIFICATE'
    elif isinstance(cause, socket.gaierror):
        category = 'DNS'
    elif isinstance(cause, TimeoutError):
        category = 'TIMEOUT'
    elif isinstance(cause, ConnectionRefusedError):
        category = 'CONNECTION_REFUSED'
    elif isinstance(cause, ConnectionResetError):
        category = 'CONNECTION_RESET'
    elif isinstance(cause, BrokenPipeError):
        category = 'BROKEN_PIPE'
    elif isinstance(cause, ssl.SSLError):
        category = 'TLS_PROTOCOL'
    elif isinstance(cause, OSError):
        category = 'OS_ERROR'
    else:
        category = 'OTHER'
    number = getattr(cause, 'errno', None)
    number = number if type(number) is int and -65536 <= number <= 65536 else None
    before_write = (progress.connection_observed and not progress.request_write_attempted
                    and not progress.response_headers and progress.phase in {
                        'TCP_CONNECT', 'PROXY_TUNNEL', 'TLS_HANDSHAKE', 'CONNECTED'})
    temporary = (category in {'TIMEOUT', 'CONNECTION_REFUSED', 'CONNECTION_RESET'}
                 or category == 'DNS' and number == socket.EAI_AGAIN
                 or category == 'OS_ERROR' and number in {errno.ENETUNREACH, errno.EHOSTUNREACH})
    return {**progress.evidence(), 'category': category, 'errno': number,
            'submission': 'NOT_SENT' if before_write else 'UNKNOWN',
            'safe_connection_retry': bool(before_write and temporary)}


class _TLSContext:
    def __init__(self, context, progress):
        self.context, self.progress = context, progress

    def __getattr__(self, name):
        return getattr(self.context, name)

    def wrap_socket(self, *args, **kwargs):
        self.progress.phase = 'TLS_HANDSHAKE'
        return self.context.wrap_socket(*args, **kwargs)


class _Connection:
    def __init__(self, *args, progress, **kwargs):
        self.progress = progress
        self._connection_setup = False
        super().__init__(*args, **kwargs)
        original = self._create_connection
        def connect_tcp(*args, **kwargs):
            progress.phase = 'TCP_CONNECT'
            sock = original(*args, **kwargs)
            progress.phase = 'PROXY_TUNNEL' if self._tunnel_host else 'CONNECTED'
            return sock
        self._create_connection = connect_tcp
        if hasattr(self, '_context'):
            self._context = _TLSContext(self._context, progress)

    def connect(self):
        self.progress.connection_observed = True
        self.progress.phase = 'TCP_CONNECT'
        self._connection_setup = True
        try:
            super().connect()
        finally:
            self._connection_setup = False
        self.progress.phase = 'CONNECTED'

    def send(self, data):
        if self._connection_setup:
            # HTTP CONNECT negotiates an HTTPS proxy before the business POST.
            return super().send(data)
        if self.sock is None:
            self.connect()
        self.progress.phase = 'REQUEST_SENDING'
        # Set BEFORE sendall: an exception may follow a partial write.
        self.progress.request_write_attempted = True
        result = super().send(data)
        self.progress.phase = 'AWAITING_RESPONSE'
        return result


class _HTTPConnection(_Connection, http.client.HTTPConnection):
    pass


class _HTTPSConnection(_Connection, http.client.HTTPSConnection):
    pass


def observed_opener(progress):
    class HTTP(urllib.request.HTTPHandler):
        def http_open(self, request):
            return self.do_open(lambda *a, **k: _HTTPConnection(*a, progress=progress, **k), request)
    class HTTPS(urllib.request.HTTPSHandler):
        def https_open(self, request):
            return self.do_open(lambda *a, **k: _HTTPSConnection(*a, progress=progress, **k),
                                request, context=self._context)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None
    return urllib.request.build_opener(HTTP(), HTTPS(), NoRedirect())


def forward(owner, client, request, metadata, number, observation_type):
    """Forward unchanged bytes; at most one pre-write retry within one native run.

    Every attempt remains charged against the same local HTTP/time ceiling.
    No response/semantic repair is purchased here. A receipt write is never
    retried as an upstream request, even when the disk outcome is uncertain.
    """
    first_number = number
    for retry in range(2):
        progress, observation = Progress(), observation_type()
        headers_sent = receipt_saved = persisting = False
        try:
            with observed_opener(progress).open(request, timeout=300) as response:
                progress.response_headers = True
                progress.phase = 'RESPONSE_HEADERS'
                client.send_response(response.status)
                client.send_header('Content-Type', response.headers.get('Content-Type', 'text/event-stream'))
                client.send_header('Transfer-Encoding', 'chunked')
                client.end_headers()
                headers_sent = True
                while True:
                    progress.phase = 'RESPONSE_READING'
                    data = response.read1(16384)
                    if not data:
                        break
                    observation.feed(data)
                    progress.phase = 'CLIENT_DELIVERY'
                    client.wfile.write(f'{len(data):x}\r\n'.encode() + data + b'\r\n')
                    client.wfile.flush()
                if getattr(response, 'length', None) not in (None, 0):
                    raise http.client.IncompleteRead(b'', response.length)
                observation.finish_response()
                progress.response_complete = True
                progress.phase = 'RECEIPT_PERSISTENCE'
                persisting = True
                owner.budget.finish(number, {'state': 'RESPONSE_COMPLETE', 'http_status': response.status,
                    **observation.result(), 'transport': progress.evidence()})
                persisting = False
                receipt_saved = True
                client.wfile.write(b'0\r\n\r\n')
                client.wfile.flush()
            return
        except urllib.error.HTTPError as error:
            progress.response_headers = True
            progress.phase = 'RESPONSE_HEADERS'
            owner.budget.finish(number, {'state': 'HTTP_REJECTED', 'http_status': error.code,
                                        'transport': progress.evidence()})
            owner.budget.close('UPSTREAM_HTTP_FAILED')
            try:
                if not headers_sent:
                    client.failure(error.code, 'EVAL_UPSTREAM_HTTP_FAILED')
            finally:
                error.close()
            return
        except Exception as error:
            diagnostic = failure_evidence(error, progress)
            if receipt_saved:
                # The original successful receipt is immutable; a client drop
                # cannot turn confirmed upstream EOF into Provider UNKNOWN.
                reason = 'LOCAL_DELIVERY_FAILED'
            elif persisting:
                # Atomic replace may already have succeeded. Never finish twice
                # or reissue the network request to repair uncertain persistence.
                reason = 'LOCAL_RECEIPT_FAILED'
            else:
                owner.budget.finish(number, {'state': diagnostic['submission'],
                    **observation.result(), 'transport': diagnostic})
                if diagnostic['safe_connection_retry'] and retry == 0 and not headers_sent:
                    time.sleep(.2)
                    try:
                        if owner.before_send:
                            owner.before_send()
                        number = owner.budget.reserve({**metadata, 'connection_retry_of': first_number,
                            'transport_policy': POLICY}, expected_number=(number + 1
                                if owner.expected_number is not None else None))
                    except Exception:
                        owner.budget.close('BATCH_FAILED')
                        client.failure(429, 'EVAL_REQUEST_OR_BUDGET_REJECTED')
                        return
                    continue
                reason = 'UPSTREAM_NOT_SENT' if diagnostic['submission'] == 'NOT_SENT' else 'UPSTREAM_UNKNOWN'
            owner.budget.close(reason)
            if not headers_sent:
                try:
                    client.failure(502, 'EVAL_' + reason)
                except OSError:
                    pass
            client.close_connection = True
            return
