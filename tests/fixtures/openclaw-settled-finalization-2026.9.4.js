// OpenClaw 2026.9.4 finalization decision, retained for offline regression.
function resolveSettledToolTerminalContinuationInstruction(params) {
	const { attempt } = params;
	const { assistant, allToolsProvenSettled, failedToolNames, hasUnsettledToolError, intentionalTermination } = resolveSettledToolBatchEvidence(attempt);
	const terminal = attempt.terminal;
	const idlePromptTimeout = terminal.kind === "timeout" && terminal.phase === "prompt" && terminal.source === "idle" && attempt.currentAttemptReplayMetadata?.hadPotentialSideEffects === true;
	const emptyStopAfterSettledTools = Boolean(params.allowEmptyStopContinuation && attempt.currentAttemptAssistant?.stopReason === "stop" && attempt.toolMetas.length > 0 && attempt.toolMetas.every((tool) => tool.isError !== true && tool.asyncStarted !== true) && attempt.itemLifecycle.startedCount > 0 && attempt.itemLifecycle.completedCount === attempt.itemLifecycle.startedCount && attempt.itemLifecycle.activeCount === 0 && !hasAcceptedSessionSpawn(attempt.acceptedSessionSpawns) && classifyAssistantTurn(params).emptyResponse);
	if (params.payloadCount !== 0 || !params.allowEmptyStopContinuation && hasOnlySilentAssistantReply(attempt.assistantTexts) || params.hasTerminalToolPresentation || params.aborted || (params.timedOut || terminal.kind === "timeout") && !idlePromptTimeout || terminal.kind === "failed" && !attempt.settledTurnFinalizationContext || (assistant?.stopReason === "toolUse" ? !allToolsProvenSettled : !emptyStopAfterSettledTools) || intentionalTermination || hasUnsettledToolError || hasAsyncActivity(attempt.toolMetas) || hasAcceptedSessionSpawn(attempt.acceptedSessionSpawns) || attempt.clientToolCalls || attempt.yieldDetected || attempt.didSendDeterministicApprovalPrompt) return null;
	if (attempt.hasToolMediaBlockReply || hasCompletedMessagingToolDeliveryEvidence(attempt)) return null;
	if (!shouldApplyNonVisibleTurnRetryGuard({
		provider: params.provider,
		modelId: params.modelId,
		modelApi: params.modelApi,
		executionContract: params.executionContract
	})) return null;
	return allToolsProvenSettled && failedToolNames.size > 0 ? `${SETTLED_TOOL_TERMINAL_CONTINUATION_INSTRUCTION} ${TOOL_FAILURE_INSTRUCTION}` : SETTLED_TOOL_TERMINAL_CONTINUATION_INSTRUCTION;
}
