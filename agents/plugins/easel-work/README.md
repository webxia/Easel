# Easel Work Bridge · A1

这是尚未安装到正式 OpenClaw 的原生插件。它复用已有 Gateway、插件 SDK 和 WorkService，只验证接入边界。当前三个工具为 context、create_draft、request_plan；其余作品工具、持久绑定与正式聊天/UI 接入见 [S6-14A](../../../docs/v2/tasks/S6-14A_conversation-integration.md)。

- `before_agent_run` 通过可信原生身份认领宿主预留的 turn；原生 session UUID 首次绑定后固定。
- `before_tool_call` 以 runId/toolCallId、动作和参数领取服务端票据；execute 只能使用该原生关联。`agent_end` 撤销本轮。
- 宿主先核对受 Gateway 认证保护的 `/plugins/easel-work/status`。插件缺失、不兼容或绑定失败时停止，不回退 main。
- 服务凭证只在插件内部使用；模型不能指定作品、命令、turn 或授权。插件只连接显式回环地址，不接受任意 URL、文件或 shell。

从仓库根的已有虚拟环境运行隔离验证：

```bash
EASEL_RUN_OPENCLAW_A1=1 .venv/bin/python -m pytest -q tests/production/test_openclaw_work_bridge_native.py
.venv/bin/python -m pytest -q tests/production/test_work_bridge.py
node --test tests/production/workBridgePlugin.test.mjs
```

原生验证需本机已安装的 OpenClaw 2026.9.x 与 Node 24；不会下载/安装依赖。每次新建系统临时目录，SDK 通过临时符号链接解析，配置/工作区/数据库/假模型都独立；测试关闭自己启动的 Gateway。不要运行 agents/sync.sh 或将测试凭证、原始请求/转录、临时配置提交到 Git。

Python 对应 `easel/work_bridge.py` 不在正式 Web 挂载，其 invocation/ticket 是内存原型。正式启用前必须完成 A2 持久化、真实范围/意图验证和入口保护。本轮不证明真实模型理解、媒体生产、问题桥、OS 沙箱或 Creator 接受。
