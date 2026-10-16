"""Harness-owned structured candidate request and pinned Runtime identity."""
from __future__ import annotations

import hashlib
import json

CONTRACT = 'planning-result-v3'
LEGACY_VERSION = 'easel-structured-result@1'
VERSION = 'easel-structured-result@2'
CONTEXT_POLICY = 'planning-original-input-only@1'
TOOL = 'submit_semantic_plan'
LEGACY_RUNTIME_PARTS = {'dist/provider-transport-fetch-C-DHvnM1.mjs': '0a50d1f8a71a1de076bac0f01376c36e5b797e504b33090027772afb5ea7ad45',
 'dist/fetch-guard-C3-bkDI5.mjs': 'e71b77957be81bb70838b43840b6a97cafb8577eea8953c606a2177721c95682',
 'node_modules/@openclaw/ai/dist/host-policy-Zcg_cNz8.mjs': '4fd8c9243682dec7901f73bd29885f79bcc97ec301d68ff26e11173e5bc58df8',
 'dist/src-7tzZ8j12.mjs': '02a4796e3fa3407f8ef1390fdc53093fa43a85dfe4c00be1edc23fd762d161cc',
 'dist/principal-CweFVZNq.mjs': '086a8c6f780f79142716303921cb84e9ab6d20cae9f2879e4276f6a4199e70bd',
 'dist/builtin-openclaw-B-H-7lKk.mjs': 'dadd861cb8ae029e1c40385705a44cb7a1d8c17ae532d26c6e879c5fc5d0e4b0',
 'node_modules/@openclaw/ai/dist/transports.mjs': 'd4ac51e6605d6c4eeaf3d1d6f8c733dc342406ee3c1456e63462edfe681a0434',
 'node_modules/@openclaw/ai/dist/openai-completions-stream-Da2vvl-S.mjs': 'dbf0630c2f7daf2ab5539fe64c1644a92fc89b08e568151ea6c37efcc73fbf87',
 'dist/easel-structured-result.mjs': '03c8406e5c5e1b8fa7828c4358e466ce8de3c84cf300fa8df5eec6f4c2f797c2',
 'dist/runtime-rYK9YYw9.mjs': '8440f13bc2e687057bc52f76aa0bbb394c8780f85e38e5616399e7779dfcf998',
 'dist/runtime-Bye51EWk.mjs': '1b4dd796612ec6238e749f52d12a208185574e40a09e2d37caca8f00b8f746f1'}
RUNTIME_PARTS = {'dist/embedded-agent-CE9KzQvy.mjs': '90f18ec6d0d4423cc529bb8f37d21875d27625a61bfdaf228a575cc7c677789a',
 'dist/provider-transport-fetch-C-DHvnM1.mjs': '0a50d1f8a71a1de076bac0f01376c36e5b797e504b33090027772afb5ea7ad45',
 'dist/fetch-guard-C3-bkDI5.mjs': 'e71b77957be81bb70838b43840b6a97cafb8577eea8953c606a2177721c95682',
 'node_modules/@openclaw/ai/dist/host-policy-Zcg_cNz8.mjs': '4fd8c9243682dec7901f73bd29885f79bcc97ec301d68ff26e11173e5bc58df8',
 'dist/src-7tzZ8j12.mjs': '68eb2cbf92d3d2d682da1952e7362a030d737f9a2bcb9aa786f367de03233bf0',
 'dist/principal-CweFVZNq.mjs': '168a7a2f7bf372088e6a657e61787ae5cbd2957a4774b3ef55de30e73bf8bedc',
 'dist/builtin-openclaw-B-H-7lKk.mjs': 'e19b026e77ab911bc0d8a4c37f121c5b32caad96670c4aaf69ec59d36c87b88a',
 'node_modules/@openclaw/ai/dist/transports.mjs': 'd4ac51e6605d6c4eeaf3d1d6f8c733dc342406ee3c1456e63462edfe681a0434',
 'node_modules/@openclaw/ai/dist/openai-completions-stream-Da2vvl-S.mjs': 'dbf0630c2f7daf2ab5539fe64c1644a92fc89b08e568151ea6c37efcc73fbf87',
 'dist/easel-structured-result.mjs': '71e0c5b2df2fcab26cdf475b6ab1a74ed0bd46feceded38551a5914dd9ec741c',
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
    return {'version': VERSION, 'name': TOOL, 'schema': schema, 'contextPolicy': CONTEXT_POLICY,
            'schemaSha256': hashlib.sha256(encoded.encode()).hexdigest()}


# Presentation-only change: JSON Schema's root title is not a result property.
# Keep the original B wire projection (and its cached decoder) untouched.
B_ROOT_TITLE_POLICY = 'planning-b-root-title-omitted@1'


def b_review_parameters(schema):
    if (not isinstance(schema, dict) or schema.get('title') != 'PlanningVisualReview'
            or schema.get('type') != 'object'
            or schema.get('additionalProperties') is not False
            or not isinstance(schema.get('properties'), dict)
            or not schema['properties']):
        raise ValueError('Unexpected B review parameters Schema; no title projection')
    # A new root dictionary; no in-place mutation of cached wire projections.
    return {key: value for key, value in schema.items() if key != 'title'}


def bind_input(request, message):
    validate_request(request)
    if not isinstance(message, str) or not message:
        raise ValueError('Planning requires its original nonempty input')
    bound = {**request, 'inputSha256': hashlib.sha256(message.encode()).hexdigest()}
    if 'inputSha256' in request and request != bound:
        raise ValueError('Planning original input identity changed')
    return bound


def validate_request(request, *, dispatch=False):
    fields = {'version', 'name', 'schema', 'schemaSha256', 'contextPolicy'}
    if isinstance(request, dict) and 'inputSha256' in request:
        fields.add('inputSha256')
    if (not isinstance(request, dict) or set(request) != fields
            or not isinstance(request.get('schema'), dict) or request['schema'].get('type') != 'object'
            or {k: v for k, v in request.items() if k != 'inputSha256'} != request_for(request['schema'])
            or 'inputSha256' in request and (not isinstance(request['inputSha256'], str)
                or len(request['inputSha256']) != 64
                or any(c not in '0123456789abcdef' for c in request['inputSha256']))
            or dispatch and 'inputSha256' not in request):
        raise ValueError('Structured Planning request identity changed')


def runtime_parts(version):
    if version == LEGACY_VERSION:
        return LEGACY_RUNTIME_PARTS
    if version == VERSION:
        return RUNTIME_PARTS
    raise ValueError('Unknown Planning Runtime protocol')


def verify_runtime(root, *, version=VERSION):
    if any(not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != sha
           for name, sha in runtime_parts(version).items()):
        raise ValueError('Structured Planning Runtime patch identity is not verified')
