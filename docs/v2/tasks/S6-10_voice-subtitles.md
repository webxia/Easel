# S6-10 · 固定音色、句段资产与字幕预览
> **调度状态：CLOSED · 2026-10-19**。用户决定关闭本卡独立研发排程：既有实现和软件验收结果保持原样，仅作为历史交付与回归依据；不再从旧实施步骤重新派发任务。后续确有实证缺陷时，仅纳入[当前三项主线](../04_CURRENT_STATE.md#唯一研发下一动作)做局部修复。CLOSED 不代表全部真实模型、音画质量、完整规格或 Creator 接受已通过。

状态：**IMPLEMENTED / OFFLINE_INTEGRATION_VERIFIED**；本卡保存配音适配、设置及本地字幕处理的软件证据。后续真实TTS出片、配音复用与字幕合成修复见[S6-14](S6-14_integration-release.md)/[S6-14A](S6-14A_conversation-integration.md)；自然听感与完整音画语义仍不能由软件或技术检查代替。

- **依赖**：S6-02、S6-06、S6-08、S6-09。
- **需求主/协作覆盖**：V2-EXP-010, V2-EXP-015, V2-EXP-023, V2-EXP-026。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/voice.py、subtitles.py、settings.py；production_api；前端声音/字幕配置组件；tests/production/test_voice_subtitles.py；tests/frontend/productionSettings.test.mjs。
- **执行分支建议**：`codex/s6-10-voice-subtitles`。

## 实施步骤

1. 本卡负责VOICE服务适配：VoiceIdentity固定provider/model/voice/engine及可用参数，禁止tts auto fallback；旁白按可定位文本段登记和复用，原声独立保存。基于画像/频道/风格推荐少量可用声音，支持服务允许的语速/情绪调整。
2. 同文/当前片段试听、已生成结果复用、真实画面字幕预览和字体/字号/位置/描边/背景/关闭；试听新收费先说明，voice不入图/视频额度，普通授权内调用不逐次询问。
3. 本片→频道→画像设置解析并快照；只有明确保存scope才改默认，默认更新不改旧方案。
4. 句段修订只重做必要音轨，对齐字幕后检查接缝；固定声音不可用时保留原设置，说明问题并提供替代试听/费用条件，用户明确选择后创建新本片设置，不自动改默认。

## 通过标准与负例

明确voice失败不换引擎；未选择替代前不调用、不改默认；复用音轨不再调用；原声不被配音替换；字号修改不改声音/文字；预览和输出一致；保存scope不漂移；真实适配代码及离线协议必须完成，实际自然听感留授权验收，fake不证明自然。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_voice_subtitles.py
node --test tests/frontend/productionSettings.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

**交付要求**：试听/预览/保存UI与真实媒体处理接通；未获服务授权仅fake配音协议通过，真实音色质量标未测。

## 执行记录

实施基线为 `codex/s6-production@4525b09da8bfc30ba556dba2198872a23b35a0ae` 的未提交工作区。新增 `voice.py`、`voice_tasks.py`、`settings.py`、`subtitles.py`、`web/production_settings_api.py`、`ProductionSettings.tsx` 和前端 helper，已接主线 runtime/CreationTasks/作品页面。配置合同见[运行配置](../16_RUNTIME_SETUP.md)。没有安装或修改用户 Runtime，也未调用真实声音/生成服务。

已实现：

- 固定 provider/model/voice_id/engine/参数，显式具名 `/audio/speech` 配置；无 auto fallback。VOICE 使用统一操作记录和当前授权，图片/视频额度不增加。超时 unknown 不重发；可恢复本地回执但不虚构服务端查询能力。
- 同文同音色缓存、按句复用、明确“重新生成试听”新意图；原声场景不走 TTS。实际时长超出方案保留音轨并请求决定，不截断/加速。重复句复用音频字节，同时各有编辑句柄。
- 试听经具名 preview grant 与持久 `voice_preview` worker，返回可播放受管 WAV；字幕预览按本片真实画面，已有成片使用同版无字幕底片，绘制与导出复用同一函数。字体只来自显式配置与固定摘要，不以系统字体替代。
- work→channel→profile 解析快照、固定整个声音身份；保存只写选定 scope，频道/画像摘要比较防止覆盖他处变更。字体、字号、位置、颜色、描边、背景和关闭控制已接入 UI；改控件不自动发收费试听。

实际执行：

```bash
/tmp/easel-s6-worker-venv/bin/python -m pytest -q tests/production/test_voice_subtitles.py tests/production/test_voice_settings_api.py
node --test tests/frontend/productionSettings.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

Python **14 passed（2.97秒）**；前端 helper/动作测试 **4 passed**；lint/build成功。lint仍有原有 `linkifyOutputs.ts` 无用转义警告，构建仍有大 chunk 提示。本卡未修改这些无关项。

Python证据包括真实 FastAPI→授权/排队→LangGraph worker→MockTransport 音频→文件播放，以及实际 CreationTasks→FFmpeg 1080竖屏有声导出：两句 WAV 独立资产、按时间线合成、模型试图改成小号红字时仍保持已确认72像素白字和背景；未把模型 scripted 检查记为自然听感或语义验收。负例覆盖未授权/错scope、unknown重发、改引擎/不支持参数、同操作改文、音频丢失、跨作品画面、缺固定字体、原声绕过TTS和配音超长。

真实声音自然度、人设适配、跨句语气/接缝、说话人一致性、字幕语义与逐词对齐仍 **NOT_TESTED**。当前提供句段真实时长，不宣称词级强制对齐已实现；实际作品音画检查和Creator接受由S6-14及使用中的具体作品承担。
