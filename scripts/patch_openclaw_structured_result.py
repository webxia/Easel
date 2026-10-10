"""Version-pinned OpenClaw structured-result compatibility patch; no restart.

Default is a complete dry run. Apply first to an isolated installation copy.
The live installation may only be changed during the verified offline load step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

VERSION = '2026.9.4'
AI = 'node_modules/@openclaw/ai/dist/'
PINS = {
    'dist/provider-transport-fetch-C-DHvnM1.mjs': '7a6d3eb1c52dd216ce0f42e48fc5e1c4ad323f22e526b3afd73ef018655c5e39',
    'dist/fetch-guard-C3-bkDI5.mjs': '7427ee4aab7cb7cbc3cc3b3770bc36582107738e54470dab75d06b21d6bc8973',
    AI + 'host-policy-Zcg_cNz8.mjs': '4fd8c9243682dec7901f73bd29885f79bcc97ec301d68ff26e11173e5bc58df8',
    'dist/src-7tzZ8j12.mjs': 'a70445b3beec4873a65f187acfde0255947f55b00e42861feaf4e54626230458',
    'dist/principal-CweFVZNq.mjs': 'bfc14ec79a60aef407c94b1679e6b4d87f7ebefbad7d68e45c5c32e5c52e02f9',
    'dist/builtin-openclaw-B-H-7lKk.mjs': '654bb2d9753e0a354320a70bdb96a120e9d5c0780e3d76f0e69bf08f4e2dd6d6',
    AI + 'transports.mjs': 'c128519c719abcd85e99a068b7e4b889d96c3b31c4ca1c6697634109969862ec',
    AI + 'openai-completions-stream-Da2vvl-S.mjs': '94fcb8422e4055a977cdd21a8581ec9dc88f57d9e70660369e5286400b6be96d',
}


# Accepted A-only carrier; upgrade only these exact inspected bytes.
PRIOR_PARTS = {'dist/principal-CweFVZNq.mjs':
    {'ef1226e5b08865214ebf96e9e112137563e6317c5c523a6b9fcf608cd1717ba3',
    'd2065be2b5ce0f5b447c45d61e79a0a423d1f9e148b2a766c34cd255876eb7d0'},
    AI + 'transports.mjs': {'5f3bc7fef92f40200583f3d6012fe88c678abe686373c901f214d3c94e12c7f9'}}
PRIOR_HELPER = {'b8664827744dc0bc51e71191e498902b1e3ae6af95510df1d46bddde668961e5',
                'b1d10de4523e9c3099df17d143b8c72aa89775c1923a811ef451c891af990036',
                '6c9d804bfbb1d11461c919b53088f11d4d76b1d95190dd8b1d21fe7a3ef98ec4'}

def digest(value):
    return hashlib.sha256(value).hexdigest()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Inspected Runtime insertion point changed')
    return source.replace(old, new, 1)


def transform(name, source):
    if name.endswith('host-policy-Zcg_cNz8.mjs'):
        return source  # Behavior dependency: forwards options to the real host.
    if name.endswith('provider-transport-fetch-C-DHvnM1.mjs'):
        source = once(source, 'function sanitizeOpenAISdkSseResponse(response, options) {',
            'function sanitizeOpenAISdkSseResponse(response, options) {\n'
            '\tconst easelWireLimit = options?.easelStructuredResult ? 64 * 1024 * 1024 : null;')
        source = once(source, 'nextTotalBytes > SSE_SYNTHESIZE_JSON_MAX_BYTES',
            'nextTotalBytes > (easelWireLimit ?? SSE_SYNTHESIZE_JSON_MAX_BYTES)')
        source = once(source, 'buffer.length > SSE_SANITIZE_BUFFER_MAX_CHARS',
            'buffer.length > (easelWireLimit ?? SSE_SANITIZE_BUFFER_MAX_CHARS)')
        source = once(source, 'sanitizeOpenAISdkSseResponse(response, { synthesizeJsonAsSse })',
            'sanitizeOpenAISdkSseResponse(response, { synthesizeJsonAsSse, easelStructuredResult: options?.easelStructuredResult })')
        return once(source, '\t\t\tallowCrossOriginUnsafeRedirectReplay: false,',
            '\t\t\tallowCrossOriginUnsafeRedirectReplay: false,\n'
            '\t\t\t...options?.easelStructuredResult ? {maxRedirects: 0, capture: false, easelStructuredResult: true} : {},')
    if name.endswith('fetch-guard-C3-bkDI5.mjs'):
        return once(source, 'async function prepareGuardedFetchCapture(params, fetchImpl) {',
            'async function prepareGuardedFetchCapture(params, fetchImpl) {\n'
            '\tif (params.easelStructuredResult) {\n'
            '\t\tconst {resolveDebugProxyFetchTransport} = await import("./runtime-rYK9YYw9.mjs");\n'
            '\t\treturn {fetchImpl: resolveDebugProxyFetchTransport(fetchImpl)};\n\t}')
    if name.endswith('src-7tzZ8j12.mjs'):
        return once(source, 'const AgentParamsSchema = closedObject({\n',
            'const AgentParamsSchema = closedObject({\n'
            '\teaselStructuredResult: Type.Optional(closedObject({\n'
            '\t\tversion: Type.Literal("easel-structured-result@1"),\n'
            '\t\tname: Type.Literal("submit_semantic_plan"),\n'
            '\t\tschema: Type.Record(Type.String(), Type.Unknown()),\n'
            '\t\tschemaSha256: Type.String({pattern: "^[a-f0-9]{64}$"})\n\t})),\n')
    if name.endswith('principal-CweFVZNq.mjs'):
        source = 'import {validateRequest as easelValidateRequest} from "./easel-structured-result.mjs";\n' + source
        source = once(source, '\t\t\tfinalizePreparedAgentRunUserTurn(prepared.userTurn);',
            '\t\t\tconst easelStructured = params.request.easelStructuredResult;\n'
            '\t\t\tif (easelStructured) {\n'
            '\t\t\t\teaselValidateRequest(easelStructured);\n'
            '\t\t\t\tif (params.request.modelRun || params.request.deliver || !params.resolvedSessionId ||\n'
            '\t\t\t\t\tparams.isRestartRecoveryResumeRun || params.restoredCronContinuation ||\n'
            '\t\t\t\t\tparams.request.swarmCollector || params.request.forceCodeModeTools)\n'
            '\t\t\t\t\tthrow new Error("STRUCTURED_ROUTE_REJECTED");\n\t\t\t}\n'
            '\t\t\tfinalizePreparedAgentRunUserTurn(prepared.userTurn);')
        return once(source,
            '\t\t\t\t\ttoolsAllow: pluginSubagentToolsAllow ?? params.restoredCronContinuation?.toolsAllow,',
            '\t\t\t\t\ttoolsAllow: easelStructured ? [easelStructured.name] : pluginSubagentToolsAllow ?? params.restoredCronContinuation?.toolsAllow,\n'
            '\t\t\t\t\t...easelStructured ? {\n'
            '\t\t\t\t\t\tclientTools: [{type: "function", function: {name: easelStructured.name,\n'
            '\t\t\t\t\t\t\tdescription: ["PlanningVisualReview", "PlanningLocalRepair"].includes(easelStructured.schema.title) ? "Submit the current stage result using the exact supplied schema" : "Submit semantic plan candidate", parameters: {type: "object", additionalProperties: true}}}],\n'
            '\t\t\t\t\t\tstreamParams: {easelStructuredResult: easelStructured}\n'
            '\t\t\t\t\t} : {},')
    if name.endswith('builtin-openclaw-B-H-7lKk.mjs'):
        source = 'import {bindAttempt as easelBindAttempt, assertSessionProtocol as easelAssertSessionProtocol} from "./easel-structured-result.mjs";\n' + source
        return once(source, '\treturn {\n\t\tserverToolClearingEnabled,',
            '\teaselAssertSessionProtocol(path.join(resolveStateDir(), "easel-structured-requests"),\n'
            '\t\t{runId: attempt.runId, sessionId: attempt.sessionId, provider: attempt.model.provider, model: attempt.model.id},\n'
            '\t\tattempt.streamParams?.easelStructuredResult);\n'
            '\tif (attempt.streamParams?.easelStructuredResult) {\n'
            '\t\tsession.agent.streamFn = easelBindAttempt(session.agent.streamFn,\n'
            '\t\t\tattempt.streamParams.easelStructuredResult, {runId: attempt.runId,\n'
            '\t\t\t\tsessionId: attempt.sessionId, provider: attempt.model.provider, model: attempt.model.id},\n'
            '\t\t\tpath.join(resolveStateDir(), "easel-structured-requests"));\n\t}\n'
            '\treturn {\n\t\tserverToolClearingEnabled,')
    if name.endswith('transports.mjs'):
        source = ('import {protectedStream as easelProtectedStream, reserveSubmission as easelReserveSubmission, retainExecutionFailure as easelRetainExecutionFailure}'
                  ' from "../../../../dist/easel-structured-result.mjs";\n') + source
        source = once(source, '\t\t\t\tconst baseFetch = buildGuardedModelFetch(model);',
            '\t\t\t\tconst baseFetch = buildGuardedModelFetch(model, void 0,\n'
            '\t\t\t\t\toptions?.easelStructuredResult ? {easelStructuredResult: true} : void 0);')
        source = once(source,
            'function createOpenAICompletionsTransportStreamFn() {\n\treturn (model, context, options) => {\n'
            '\t\tconst { eventStream, stream } = createWritableTransportEventStream();',
            'function createOpenAICompletionsTransportStreamFn() {\n\treturn (model, context, options) => {\n'
            '\t\tconst { eventStream, stream: easelBaseStream } = createWritableTransportEventStream();\n'
            '\t\tconst stream = options?.easelStructuredResult ? easelProtectedStream(easelBaseStream, options.easelStructuredResult) : easelBaseStream;')
        source = once(source, '\t\t\t\tconst doneDetectingFetch = async (url, init) => {\n',
            '\t\t\t\tconst doneDetectingFetch = async (url, init) => {\n'
            '\t\t\t\t\tif (options?.easelStructuredResult) {\n'
            '\t\t\t\t\t\tconst scope = options.easelStructuredResult;\n'
            '\t\t\t\t\t\teaselReserveSubmission(scope.directory, scope.identity, JSON.parse(init.body), scope.request);\n'
            '\t\t\t\t\t}\n')
        source = once(source,
            '\t\t\t\t\tcleanup: () => {\n'
            '\t\t\t\t\t\toutput.stopReason = options?.signal?.aborted ? "aborted" : "error";\n'
            '\t\t\t\t\t\tfinalizeOpenAICompletionsToolCalls(output, { allowSilentToolCallPromotion: false });',
            '\t\t\t\t\tcleanup: () => {\n'
            '\t\t\t\t\t\tif (options?.easelStructuredResult) easelRetainExecutionFailure(options.easelStructuredResult, output, error);\n'
            '\t\t\t\t\t\toutput.stopReason = options?.signal?.aborted ? "aborted" : "error";\n'
            '\t\t\t\t\t\tfinalizeOpenAICompletionsToolCalls(output, { allowSilentToolCallPromotion: false });')
        return once(source, '\t\t\t\tawait processCompletionsStream(hookedResponseStream, output, model, stream, {\n',
            '\t\t\t\tawait processCompletionsStream(hookedResponseStream, output, model, stream, {\n'
            '\t\t\t\t\teaselStructuredResult: options?.easelStructuredResult,\n')
    if name.endswith('openai-completions-stream-Da2vvl-S.mjs'):
        source = once(source, 'function createOpenAICompletionsToolCallDeltaNormalizer() {',
            'function createOpenAICompletionsToolCallDeltaNormalizer(maxArgumentBytes = MAX_BUFFERED_TOOL_CALL_ARGUMENT_BYTES) {')
        source = once(source, 'state.bytes > MAX_BUFFERED_TOOL_CALL_ARGUMENT_BYTES', 'state.bytes > maxArgumentBytes')
        source = once(source, 'pendingLegacyArgumentBytes + nextArgumentBytes > MAX_BUFFERED_TOOL_CALL_ARGUMENT_BYTES',
            'pendingLegacyArgumentBytes + nextArgumentBytes > maxArgumentBytes')
        source = once(source, 'const normalizeToolCallDeltas = createOpenAICompletionsToolCallDeltaNormalizer();',
            'const normalizeToolCallDeltas = createOpenAICompletionsToolCallDeltaNormalizer(options?.easelStructuredResult ? 8 * 1024 * 1024 : void 0);')
        source = once(source, '\t\tdelete block.partialArgs;',
            '\t\tif (options.easelStructuredResult) block.easelRawArguments = block.partialArgs;\n\t\tdelete block.partialArgs;')
        source = once(source, '\t\tconst rawChoiceDelta = choice.delta ?? choice.message;',
            '\t\tif (options?.easelStructuredResult && choice.finish_reason != null)\n'
            '\t\t\toutput.easelProviderFinishReason = choice.finish_reason;\n'
            '\t\tconst rawChoiceDelta = choice.delta ?? choice.message;')
        return once(source, '\tfinalizeOpenAICompletionsToolCalls(output, {\n\t\tallowSilentToolCallPromotion:',
            '\tfinalizeOpenAICompletionsToolCalls(output, {\n'
            '\t\teaselStructuredResult: options?.easelStructuredResult,\n\t\tallowSilentToolCallPromotion:')
    raise ValueError('Unknown patch target')


def patch_installation(root: Path, *, apply=False):
    if json.loads((root / 'package.json').read_text()).get('version') != VERSION:
        raise ValueError('Unsupported Runtime version')
    planned = {}
    for name, expected in PINS.items():
        target = root / name
        current = target.read_bytes()
        backup = target.with_name(target.name + '.easel-structured-original')
        original = backup.read_bytes() if backup.exists() else current
        if digest(original) != expected:
            raise ValueError('Runtime source fingerprint differs: ' + name)
        updated = transform(name, original.decode()).encode()
        if current not in (original, updated) and digest(current) not in PRIOR_PARTS.get(name, set()):
            raise ValueError('Partial or foreign Runtime patch: ' + name)
        planned[name] = (original, current, updated)
    helper = Path(__file__).with_name('openclaw_structured_result.mjs').read_bytes()
    helper_target = root / 'dist/easel-structured-result.mjs'
    previous_helper = helper_target.read_bytes() if helper_target.exists() else None
    if previous_helper is not None and previous_helper != helper and digest(previous_helper) not in PRIOR_HELPER:
        raise ValueError('Installed helper differs; review a new patch revision before replacement')
    if apply:
        # Validate every input before writing any target. Originals are never replaced.
        for name, (original, current, updated) in planned.items():
            target = root / name
            if current == updated:
                continue
            if current != original:
                prior = target.with_name(target.name + '.easel-structured-prior-' + digest(current))
                if prior.exists() and prior.read_bytes() != current:
                    raise ValueError('Prior Runtime backup differs')
                if not prior.exists():
                    with prior.open('xb') as stream:
                        stream.write(current); stream.flush(); os.fsync(stream.fileno())
            backup = target.with_name(target.name + '.easel-structured-original')
            if not backup.exists():
                with backup.open('xb') as stream:
                    stream.write(original)
                    stream.flush()
                    os.fsync(stream.fileno())
            fd, temporary = tempfile.mkstemp(dir=target.parent, prefix='.easel-structured-')
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(updated)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.chmod(temporary, target.stat().st_mode & 0o777)
                if target.read_bytes() != current:
                    raise ValueError('Runtime changed during patch')
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        if previous_helper != helper:
            if previous_helper is not None:
                prior = helper_target.with_name(helper_target.name + '.easel-structured-prior-' + digest(previous_helper))
                if prior.exists() and prior.read_bytes() != previous_helper:
                    raise ValueError('Prior helper backup differs')
                if not prior.exists():
                    with prior.open('xb') as stream:
                        stream.write(previous_helper); stream.flush(); os.fsync(stream.fileno())
            fd, temporary = tempfile.mkstemp(dir=helper_target.parent, prefix='.easel-structured-')
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(helper); stream.flush(); os.fsync(stream.fileno())
                current_helper = helper_target.read_bytes() if helper_target.exists() else None
                if current_helper != previous_helper:
                    raise ValueError('Runtime helper changed during patch')
                os.replace(temporary, helper_target)
            finally:
                Path(temporary).unlink(missing_ok=True)
    return {'version': VERSION, 'applied': apply, 'service_restarted': False,
            'files': {name: {'before': digest(original), 'after': digest(updated)}
                      for name, (original, current, updated) in planned.items()},
            'helper_sha256': digest(helper)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(patch_installation(args.installation.resolve(), apply=args.apply), indent=2))
