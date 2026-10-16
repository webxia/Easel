"""Durable model transport: replay receipts, never blindly retry an uncertain call."""
from __future__ import annotations
import hashlib
import json
from .model_tasks import ModelTaskError
from .providers.base import ProviderResult
from .operations import OperationService


class RecordedModelTransport:
    def __init__(self, transport, operations: OperationService, binding, service: dict, config_version: str):
        self.transport, self.operations, self.binding = transport, operations, binding
        self.service, self.config_version = service, config_version
        self.capabilities = transport.capabilities
        self.index = 0

    async def complete(self, messages, tools, schema):
        request = {'messages': messages, 'tools': tools, 'schema': schema}
        ctx = self.binding
        self.index += 1
        operation_id = hashlib.sha256(f'{ctx.task_id}:model:{self.index}'.encode()).hexdigest()
        # Existing intent keeps its original grant even if another grant was added later.
        with self.operations.store.connection() as conn:
            prior = conn.execute('SELECT grant_id FROM operations WHERE id=?',(operation_id,)).fetchone()
            grants = conn.execute('SELECT * FROM authorization_grants WHERE work_id=? AND revoked_at IS NULL ORDER BY created_at DESC',(ctx.work_id,)).fetchall()
        grant_id = prior['grant_id'] if prior else next((g['id'] for g in grants if self.service in json.loads(g['services_json']) and
            ((g['purpose']=='planning' and ctx.plan_revision is None) or (g['purpose']=='production' and g['plan_revision']==ctx.plan_revision))),None)
        if not grant_id:
            raise ModelTaskError('permission_missing','本任务尚未授权当前模型服务，请在制作工作台补充授权')
        op = self.operations.reserve(operation_id=operation_id,work_id=ctx.work_id,run_id=ctx.run_id,
            task_id=ctx.task_id,grant_id=grant_id,kind='MODEL',**self.service,
            config_version=self.config_version,request=request,owner_epoch=ctx.owner_epoch)
        if op['state']=='succeeded':return op['receipt']['result']['message']
        if not self.operations.mark_sending(operation_id,ctx.owner_epoch):
            raise ModelTaskError('result_unknown','已有模型调用尚无确定回执；不能自动重复提交')
        try:
            message = await self.transport.complete(messages,tools,schema)
        except BaseException:
            self.operations.mark_unknown(operation_id)
            raise
        self.operations.receive(operation_id,ProviderResult('succeeded',result={'message':message}))
        return message
