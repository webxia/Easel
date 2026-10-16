# S6-10 · 固定音色、句段资产与字幕预览

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

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

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
