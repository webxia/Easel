# Easel V2 · 当前状态

**当前阶段：S6-01～13 软件主链已接通，S6-15 CLOSED/COMPLETE。唯一进行中的任务为 S6-14 首次真实视频生产。2026-10-17 在 V2 独立 7870 后端同一作品《把想法变成作品》完成 MiniMax 真模型规划（一次人工字段整理）、Pexels/合格音源真实供料、MiniMax 7 段 TTS、Director 真实画面选材与 FFmpeg 输出 45.000 秒 1080×1920 H.264/AAC MP4；技术 QC PASS。当前完整有声视频语义 QC 因 MiniMax 未配置受证实的原生音视频审片协议而 `not_tested`，作品保留 `needs_decision`、首版质量 `needs_fix`，尚无 Creator 审片接受、无人干预自主 E2E PASS 或发布。详见 [S6-14](tasks/S6-14_integration-release.md) 最新运行记录。**

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

- S6-15 代码审计/架构成果已推送为 `867d471c`，但绑定该提交的跨平台 CI 出现 1 项 Ubuntu 和 2 项 Windows 失败，均已定向归因；本地素材模块修复后 383 passed / 3 skipped。新补丁的跨平台 CI 仍须按精确 SHA 核查，不能以本机测试宣称 Windows 问题关闭；具体见 [S6-15](tasks/S6-15_material-layer-hardening.md)。

- 2026-10-17 最新范围：按用户明确决定 Unsplash 继续 preview-only，**不新建音频素材管理界面**；S6-15 仅新增 BGM/SFX Wikimedia Commons 公共搜索 Provider、角色隔离、官方文件专属许可/署名校验、下载 SHA-1 和 OGG 合格音频路径。真实无账户查询已有候选，但生产下载受本机私网映射 DNS 阻断，G3 实际音频、用户听感和真实声音服务仍 NOT_TESTED；参见 [S6-15](tasks/S6-15_material-layer-hardening.md)。

**CURRENT_PAUSE：本轮 [G4 正式验收与 NO_GO 报告](19_MATERIAL_LAYER_G4_ACCEPTANCE.md) 已建立，且用户要求完成后停止，不继续自动执行；后续仅在用户再次要求时处理公网安全下载、实际音频/声线和 CI 证据，再重新作 G4 准入判定。S6-14 仍暂停。**

- 用户新指令仅授权修复 Clash Fake-IP 下载卡点。经可信 HTTPS DoH 获得公网 IP、受控 loopback HTTP CONNECT 和源域名 TLS 校验的素材下载适配已实现；Pexels 图/视频、Commons BGM 真实安全下载及隔离库技术验收，Pixabay 图片也已真实下载。Commons SFX CDN 429、实际听感与固定声线仍未通过。见 [G4 网络修复复验](19_MATERIAL_LAYER_G4_ACCEPTANCE.md)；**S6-14 仍暂停**。 [审计](17_MATERIAL_LAYER_AUDIT.md)和[架构选型](18_MATERIAL_LAYER_ARCHITECTURE.md)已落地，内部冻结意图、SFX绑定、来源授权、素材再准入、只选中依赖及原生旁白适配已实施。合成媒体/模拟模型的五模态整链不代表真实创作品质；不重做G0，不重复索取已允许复用的配置，不在未授权时实发模型、配音或生成请求。

- 2026-10-17 用户确认当前 MiniMax Key 为 M Plan 专用订阅 Key；官方套餐余量查询成功，V2 已固定 `speech-2.8-hd` / `male-qn-qingse` 试听声线并真实生成 4.644 秒中文 MP3；用真实视频 + SFX + 旁白 FFmpeg 集成 5.005 秒 MP4、含音视频双流。详见 [G4 续验](19_MATERIAL_LAYER_G4_ACCEPTANCE.md)。这些仅为技术样片，**不等于产品内真实 Director 创意选择 / 真实完整 QC / Creator 接受**。G4 NO_GO，S6-14 暂停。

- **2026-10-17 S6-14 初始接手快照（历史）**：活动树最初未有 V2 作品及授权；独立 7870 Web 首次启动时模型仍是旧配置。该证据已被后续实测推进覆盖，不代表当前仍缺作品或使用 DeepSeek。
- **2026-10-17 当前首片真实后端进展**：同一《把想法变成作品》Work 采用六维画像、Human Cinema Director Revision 2、Plan Revision 2、45 秒竖屏混合音轨；MiniMax M Plan 真实文本/图像理解和固定中文语音、合格外部供料、Director 9 镜头剪辑及 FFmpeg MP4 真实产出。文件为 45.000 秒、1080×1920、H.264+AAC，已记录素材署名包；Supply/Edit/Render 全部 succeeded，技术 QC pass。当前语义 QC not_tested / video_protocol_unavailable，Work 为 needs_decision，Creator 未接受具体版本；自主无研发辅助项仍未通过。唯一主线仍是 S6-14 完整音画 QC 与真人审阅，不重开 S6-15。
