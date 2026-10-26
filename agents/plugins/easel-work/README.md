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

## S6-14A协议2（A2～A4源码已实现）

设置`protocolVersion=2`启用6个具名工具及持久宿主`easel/conversation_bridge.py`。草稿/规划/修订统一沿easel_pipeline；修订显式绑定output_id，改旁白用scope=narration、preserve_audio=false，展示范围后由下一真人回合answer确认。propose只创建频道/导演/长期保存提议，不应用目标。原协议1仅为A1原型，不可用内存探针替代持久宿主。

部署字段与明确边界见[运行说明](../../../docs/v2/16_RUNTIME_SETUP.md)，源码/验证证据见[S6-14A](../../../docs/v2/tasks/S6-14A_conversation-integration.md)。`scripts/prepare_video_workspace.py`只准备新工作区及待合并patch；合并时保留main和原plugins allow/load成员，正式安装、权限合成及服务加载仍须按部署安排验收。本轮未修改实际OpenClaw或生产数据库。

隔离实际Web/原生验证：`.venv/bin/python scripts/validate_video_conversation.py --root <全新系统临时目录>`。使用本机现有OpenClaw/Node，不下载依赖，服务/model/DB均是临时合成环境。不能据此宣称真实模型创作、完整浏览器矩阵或Creator接受通过。

协议2另有被动原生调用诊断：llm_input/llm_output/agent_end只提取白名单配置、计数和终止状态，在原end回调保存；不存提示/正文/思考/工具参数/凭证。配置标记configured_not_wire，不能替代最终HTTP请求抓取。用量全零标missing_or_zero。诊断失败不改变原生身份与结束权限，不自动重试模型；正式安装/重载仍需按部署授权执行。
