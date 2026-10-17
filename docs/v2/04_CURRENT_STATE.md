# Easel V2 · 当前状态

**当前阶段：S6-01～13 已接通并完成本地软件/合成媒体验证；S6-15 素材层完善任务已建立、尚未实施；S6-14 为 PARTIAL，真实生产和 Creator 验收依用户最新决定暂缓，待素材层完善后继续。**

## 接手入口

- 唯一活动工作树：`/Users/xgx/.codex/worktrees/s5-architecture/Easel`，分支 `codex/s6-production`，从 `4525b09d` 文档整理成果接手。
- [研发 PR #8](https://github.com/webxia/Easel/pull/8) 为草稿，base 为 `codex/s5-architecture`。已提交领域基础 `e923332a` 和调用/持久执行 `97199284`；整链代码 `97ecc67b` 与最终测试证据见 [S6-14](tasks/S6-14_integration-release.md)。不自动合并或发布。
- `/Users/xgx/Projects/Easel` 的 分支 docs/s1-capability-audit（HEAD `78ed77ed`） 是历史工作树，保持其画像、输出和未跟踪资料，不切换或清理。V1 归档 `57c8e2ad` 只读；只适配迁入素材核心，没有恢复旧执行链或历史库。

## 实现与验收依据

[S4 需求](01_REQUIREMENTS.md) 001～034、[逻辑职责](02_ARCHITECTURE.md)、[技术选型](14_TECHNOLOGY_SELECTION.md)、[实施合同](15_IMPLEMENTATION_DESIGN.md)为正式依据。用户已同意当前推荐作为实施基线；已落实可选 LangGraph 固定依赖、SQLite 领域权威和外部 FFmpeg 编辑后端，许可证/兼容证据保留在对应卡和 ADR。

[任务包](tasks/S6_IMPLEMENTATION_PLAN.md)和各卡维护实施结果；[运行配置](16_RUNTIME_SETUP.md)提供本地启动、模型/视频协议、素材来源、配音、字幕字体及真实调用边界。无配置时明确暂停并保留成果，不用演示模式替代实际服务。

## 证据与剩余边界

- 已接通作品命令、持久编排、生成次数/未知回执、可观察工作台、素材供给、固定声音/字幕、制作自检、局部修订、内容库与频道/导演生命周期。
- 本地实际 FFmpeg 渲染含独立 90 秒、900 秒及两画幅/四声音测试；脚本化模型整链包含接受旧版→视觉局部修改→再渲染→明确选择新版。完整规格组合、真实模型自主生产、自然音色和风格稳定性没有据此宣称通过。
- 浏览器隔离环境验证创建作品、缺服务原因、重启后的任务与恢复入口；测试服务已停止，未重启用户生产服务。
- S6 开工已 Fetch 官方上游，仍为 `b29d0d72`，相对长期 V2 3/24；相比 S5 无新增官方提交，未合入。最终 CI 必须按 [S6-14](tasks/S6-14_integration-release.md) 中精确 SHA 解读。

- 2026-10-17 在精确 HEAD `3c8fa4d2` 的工作树补充了端口 7870 的真实本机 Web 启用/停用检查（关闭为 503 且不建库；开启为 200），新建的空 V2 SQLite 库无作品/任务/操作/授权/素材记录；CLI 状态和 SQLite 在线备份完整性通过。未调用远端模型、声音、素材服务；具体证据见 [S6-14](tasks/S6-14_integration-release.md)，真实生产及 Creator 接受依然未测。

- 2026-10-17 用户明确同意复用本机配置及合格的旧本地素材：V2 独立 `.env` 已安全写入现有 Pexels/Pixabay/Unsplash/MiniMax/兼容模型身份；Pixabay 自动供料适配器与缓存、Unsplash 显式 preview-only、经 Rights/技术校验的旧本地 MP3 复制并启用 owner-wide 有界复用。旧 DB/资产原件保留。API 真实供料和完整成片仍未测试，详情见 [S6-14](tasks/S6-14_integration-release.md)。

**NEXT_SINGLE_ACTION：按 [S6-15](tasks/S6-15_material-layer-hardening.md) 的 G0 开始素材库上下游事实和缺口审计，再做 G1 合同/责任评审、G2/G3 实施与完整素材验收。** 用户明确要求先建立任务文档、完善素材库，完成前不启动 S6-14 真实生产。S6-14 既有软件证据与 PARTIAL 状态保留；未来真实创作主题/样本和模型/声音、IMAGE/VIDEO 授权仍在 S6-14 恢复时核实，不在此轮反复索取。
