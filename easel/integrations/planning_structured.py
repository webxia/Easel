"""Harness-owned structured candidate request and pinned Runtime identity."""
from __future__ import annotations

import hashlib
import json

CONTRACT = 'planning-result-v3'
VERSION = 'easel-structured-result@1'
TOOL = 'submit_semantic_plan'
RUNTIME_PARTS = {'dist/provider-transport-fetch-C-DHvnM1.mjs': 'fe2923d07e202d3c84f1aa1f69fb7f43c3e288a14b9970aef2bab6a32a1e21cd',
 'dist/fetch-guard-C3-bkDI5.mjs': 'e71b77957be81bb70838b43840b6a97cafb8577eea8953c606a2177721c95682',
 'node_modules/@openclaw/ai/dist/host-policy-Zcg_cNz8.mjs': '4fd8c9243682dec7901f73bd29885f79bcc97ec301d68ff26e11173e5bc58df8',
 'dist/src-7tzZ8j12.mjs': '02a4796e3fa3407f8ef1390fdc53093fa43a85dfe4c00be1edc23fd762d161cc',
 'dist/principal-CweFVZNq.mjs': '086a8c6f780f79142716303921cb84e9ab6d20cae9f2879e4276f6a4199e70bd',
 'dist/builtin-openclaw-B-H-7lKk.mjs': 'dadd861cb8ae029e1c40385705a44cb7a1d8c17ae532d26c6e879c5fc5d0e4b0',
 'node_modules/@openclaw/ai/dist/transports.mjs': '5f3bc7fef92f40200583f3d6012fe88c678abe686373c901f214d3c94e12c7f9',
 'node_modules/@openclaw/ai/dist/openai-completions-stream-Da2vvl-S.mjs': 'dbf0630c2f7daf2ab5539fe64c1644a92fc89b08e568151ea6c37efcc73fbf87',
 'dist/easel-structured-result.mjs': '6c9d804bfbb1d11461c919b53088f11d4d76b1d95190dd8b1d21fe7a3ef98ec4',
 'dist/runtime-rYK9YYw9.mjs': '8440f13bc2e687057bc52f76aa0bbb394c8780f85e38e5616399e7779dfcf998',
 'dist/runtime-Bye51EWk.mjs': '1b4dd796612ec6238e749f52d12a208185574e40a09e2d37caca8f00b8f746f1'}


def request_for(schema):
    # Current finite schemas use integers for numeric bounds. Normalize integral
    # floats so Python and the native JSON.stringify identity agree as well.
    def normalized(value):
        if isinstance(value, dict):
            return {key: normalized(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalized(item) for item in value]
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    schema = normalized(schema)
    encoded = json.dumps(schema, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False)
    return {'version': VERSION, 'name': TOOL, 'schema': schema,
            'schemaSha256': hashlib.sha256(encoded.encode()).hexdigest()}


def validate_request(request):
    if (not isinstance(request, dict) or set(request) != {'version', 'name', 'schema', 'schemaSha256'}
            or not isinstance(request.get('schema'), dict) or request['schema'].get('type') != 'object'
            or request != request_for(request['schema'])):
        raise ValueError('Structured Planning request identity changed')


def verify_runtime(root):
    if any(not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != sha
           for name, sha in RUNTIME_PARTS.items()):
        raise ValueError('Structured Planning Runtime patch identity is not verified')
