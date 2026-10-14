
# Easel V1 Web 真实 E2E：方案、操作手册与执行记录（2026-10-10）

> **文档职责（2026-10-11 主方案正式批准）：本文件是唯一 E2E 历史及未来运行证据账本，不再拥有独立生产执行标准。** 新生产的 R1–R6、U0–U6 唯一标准已由用户批准，见 [`New-Only → Web E2E 统一主方案`](../architecture/web-backend-new-only-cutover-plan-2026-10-11.md) §8（`APPROVED_SINGLE_EXECUTION_STANDARD`）；具体 U2/U5/U6 执行、模型/Provider/Build、服务与费用仍待单独授权。本文件下方旧 Proposal @3、410、旧 Material 链路、E0–E3 手册均为当时的历史事实与证据，**不再作为未来可执行命令**；7 次失败 Attempt、24/24 次调用、15 份原始捕获、现金/UNKNOWN、SHA 保持原样。以后每轮新增真实执行信息**只在本文件顶部**登记，不在 Creator Task 重复写运行流水，不另建平行账本。**

## 2026-10-12 同一 U2 候选受控加载与 U4 复检

**CONTROLLED_LOAD=COMPLETE；RESULT=BLOCKED（U4）；DRIFT=NO_DRIFT；TRANSITION=HOLD；U2_CANDIDATE_READY / U3-S=PASS / U3-L=NOT_STARTED / RELEASE_NOT_AUTHORIZED。** 本轮用户明确授权候选前端/安装 Skill 同步、前后端重启和本地页面读取；没有授权生产确认、模型/Provider、有价调用、真实 E2E 或 U5–U6。承接前次加载差异，不重启历史迁移。

### 同一候选加载与只读验证

- 加载前逐项核验 U2 manifest SHA `846bb445d7df5fdfd98332b68e4f989f6e07e64d24e14bb1e226c072b5cd6ddc`，1,233 项 Source/Test/Skill、8 项非敏感配置及 5 项隔离 React 产物无漂移。原服务 dist 移至本轮非公开临时备份目录；直接安装已验收的 5 项 React 产物，未重新构建或改变候选指纹。
- 同步安装文件 11 份：7 个 Skill 的 `SKILL.md`（ai-video-gen、beat-sync-video、hypit-authoring、multi-voice-dubbing、paper-explainer、slideshow-video、video-intro-outro）、multi-voice-dubbing/paper-explainer 的两份 EASEL-META、paper-explainer 的 storyboard reference 和一份 skill-wechat-publisher 安装包附带测试文件。旧文件均完整备份；**仓库源码/测试文件没有修改**。核验安装 112 个 Skill 集合、598 个存在文件及 118 个候选删除身份全部匹配，没有额外或遗漏的 Skill。
- 项目前端由 FastAPI 提供，没有独立 5173 前端开发进程。本轮重启原 `com.easel.web` LaunchAgent，旧 PID `35281` → 新 PID **`98148` / 2026-10-12 23:37:31 +08:00**；仍只监听 `127.0.0.1:7860`。当前 OpenAPI SHA `efa13175291909b748e0a5d546db06d6e5609ea9c9401bdb03aecbbdebd8be3c`，规范化后 **80 个实际路径注册 = 80 个当前源码路径，无增减/方法差异**；原 15 个旧注册已消失。没有调用旧生产端点进行试探。
- 浏览器访问前只读 GET `/` / `/api/status` / `/openapi.json` 为 200；Gateway health 为 true。服务 index SHA **`22e1fa4efad2ed8516ca5b300f79c746662f864771d1f7d64109999c6ea9ecd8`** 与候选一致，其引用的候选 JS `index-BcwhSvxF.js` 在服务 dist 的 SHA 为 `e303bf1766b7941c15b504f2674c1f523182c8a65aa6dff0a3fb592f6a12e3ba`；5 项磁盘产物全部匹配。`/onepage` 及三条旧 static HTML 入口均 404。
- Gateway 原 PID `86014` 和启动时间保持，OpenClaw 2026.9.4 的 11 个磁盘补丁 pin 全部匹配；本轮没有重启 Gateway、执行会话修复或新 Agent Job。Hypit 0.2.7、本地 Runtime profile SHA `1e4099d70ed19b6ebed1451ad430cf0f9c3bbd464d9218712874af1744d18a51` 保持，没有任何 Hypit CLI/Check/Plan/Pricing/Build。安装磁盘身份不能证明 Gateway 进程内全部字节或原会话的缓存 Prompt；不为获取这种证据派发模型请求。

### U4 缺证与现场保护

虽然本轮用户明确授权页面读取，浏览器安全审批仍返回 **“A saved user permission setting blocks this action”**，阻止访问 `http://127.0.0.1:7860`。没有成功创建页面、读取按钮或执行确认；未改用其他浏览器、原始控制或间接页面渲染绕过。**ACTUAL_UI=NOT_VERIFIED_SAVED_PERMISSION_BLOCK**，区别于产品 UI 故障。拒绝后仅完成独立本地文件与保全检查，没有再通过 HTTP 达成被拒绝的页面读取。

重启前后核对实际 Delivery 资格：`cr_ca48a2d63ade46b6bd88664aa436e9ad` 无下一操作、等待证据；`cr_3ac59f99a8fa4d79a588423f8d688dc8` 的 prepare 原失败次数为 3 且原 exhausted_operation 匹配，现行 Owner 门禁阻止执行。两条记录均保持原字节；没有手改失败状态、点击 retry、释放原占额或自动开始 Preparation。其余历史 Creation 不进入现行生产 Worker。

29 个现有 Creation / 25 个引用 Attempt 的既有 Rights、费用/UNKNOWN 观察与上一记录相同，**不重放、不重新解释或清账**。10 份原生成结果的 billing UNKNOWN（8 个不同原文 SHA）保持，Gateway 46 份原请求记录 SHA 保持。当前套餐余量、未结算占用及下一请求最高现金风险仍 **BUDGET_NOT_PROVEN**；本轮新增模型/Provider/生产确认/有价服务/Hypit 请求均为 0。没有把免费 CI 报价或凭证存在当成真实请求的现金保证。

本轮证据和完整旧安装备份在 `/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u4-load-eiudtbqm/`：`start.json`、`sync-result.json`、`served-dist-before-load/`、`installed-skill-backup/`、`loaded-web-audit.json`、`loaded-openapi.json`、`skill-sync-verification.json`、`runtime-identity.json`、`delivery-no-dispatch-check.json`、费用观察及最终指纹检查。旧安装备份不在公开服务根目录，不构成第二条执行主线。

**EVIDENCE=受控加载同版已验证，112 Skills 合同通过；实际页面与现金上限未验证，U4 不放行。LESSON=保存的浏览器访问策略须独立解除，聊天授权不会自动更改工具设置。NEXT_SINGLE_ACTION=暂停，待用户解除浏览器保存的本地地址禁用设置并具备可靠现金上限证据后，再继续同一候选的 U4 只读预检。** 不自动进入 U5–U6，不再重启或新增生产请求；无真实 Web E2E / DEBUG PROGRESS / RELEASE PASS 新结论。最终保全与文档检查结果如下方收尾。

**收尾：**HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389` / `easel-studio`、74 M / 121 D、0 staged / 0 untracked 保持；仓库相对起点只有本 Task、Current State、本账本变化，未改生产/测试/配置。候选 1,233/8/5 项身份和实际服务 5 项 React 产物均匹配；3,255 个既有运行 JSON/JSONL、46 个 Gateway 请求 SHA 无变化，现有 29 个 Creation ID 集合不变，没有新增 Creation/Attempt 或业务请求。112 Skills 合同、本轮 4 个新增引用/锚点与 git diff --check 通过。受控重启的 Web 进程保持健康启动身份，旧安装备份保留；最终报告在 `final-fingerprint-check.json`。**本轮已暂停，U4 仍 BLOCKED。**

## 2026-10-12 U4 无付费只读预检运行证据

**RESULT=BLOCKED（U4）；DRIFT=NO_DRIFT；TRANSITION=HOLD；U2_CANDIDATE_READY / U3-S=PASS / U3-L=NOT_STARTED / RELEASE_NOT_AUTHORIZED。** 本轮仅授权现场只读预检，未点击生产确认、派发请求、查询 Provider 或调用 Hypit。此结果不推翻 U2/U3-S 软件证据，但不得进入 U5–U6。

### Web 与实际加载身份

- 后端 PID `35281`，启动时间 **2026-10-11 13:11:49 +08:00**，工作目录本项目，监听 `127.0.0.1:7860`。访问浏览器前只读 GET `/` 和 `/openapi.json` 均 200；OpenAPI 原文 SHA `5d2457db2b0e5cab3519a03a47a162e35e5d16b93c5313b30b1c7ee52320f019`。路径转换器规范化后，当前源码注册 80 个路径，实际加载注册 95 个；多出的 15 个包括 `/onepage`、Creation stage/handoff、旧 Attempt author/build/export/reconcile 及直接素材生成等。完整差异列在 `loaded-version-audit.json`；**没有调用这些主动接口，不能用路由注册推断其会执行、拒绝或付费**。`/static/index.html`、`main.html`、`onepage.html` 返回 404，只证明此次请求结果。
- 页面 index SHA `19e606decf4f8df676d63917aa4956d05235e5258e0bf51c19673b0ce867e70f`；它引用磁盘 `index-WHRnRRmi.js`，SHA `b5667e8b4ef61cdbacf32f88e1a0f34c63331755790369140b96f4953c85ee7a`，mtime **2026-10-12 19:34:23 +08:00**。U2 隔离候选 index SHA `22e1fa4efad2ed8516ca5b300f79c746662f864771d1f7d64109999c6ea9ecd8`，JS `index-BcwhSvxF.js` SHA `e303bf1766b7941c15b504f2674c1f523182c8a65aa6dff0a3fb592f6a12e3ba`，后者不在服务 dist 中；另 CSS/图标三项一致。**React 加载产物不同，不只是后端需要加载当前版本。**
- 浏览器创建本地页面时安全审批拒绝，原因为 **user declined permission / 用户未授予访问许可**。没有创建页面或点击任何按钮；此后未通过其他浏览器、HTTP/UI 转换或间接方式绕过访问拒绝。实际 Creator 页面、Proposal @4 投影、按钮及拒绝行为为 **NOT_VERIFIED_BROWSER_PERMISSION_DENIED**。上述访问前的接口结果和磁盘检查不冒充实际页面验收。

### Gateway / Skill / Hypit

- Gateway PID `86014`，启动于 **2026-10-10 21:43:42 +08:00**，loopback `18789`；安装 OpenClaw **2026.9.4**。候选 pin 的 **11 个结构化结果运行文件磁盘 SHA 全部一致**，最新文件 mtime 早于该进程启动；这仍不是进程内全部加载字节的直接证明。未启动 Job、`agent.wait`、会话修复或 Gateway patch。
- 已安装 112 个 Skill 的 `SKILL.md` 中 **105 一致 / 7 不同**：`paper-explainer`、`video-intro-outro`、`multi-voice-dubbing`、`beat-sync-video`、`hypit-authoring`、`slideshow-video`、`ai-video-gen`。部分安装文本仍引用旧 auto-short-video 组装路径，hypit-authoring 尚缺候选的 Material 准入限制；这里只证明安装合同未同步，不推断执行结果。逐文件 SHA 和差异在 `openclaw-skill-audit.json` / `skill-*.diff`，未修改任何安装文件。
- Hypit 安装 **0.2.7**；只读当前进程环境下解析的 Runtime profile `/Users/xgx/.easel/hypit-v1-runtime/hypit.runtime.json`，SHA `1e4099d70ed19b6ebed1451ad430cf0f9c3bbd464d9218712874af1744d18a51`，local media/hyperframes、空 bindings/credentials。该磁盘配置不证明后端继承环境或下一请求报价；本轮没有执行 Hypit CLI、Check/Plan/Pricing/Build。Gateway 主模型配置 MiniMax-M3/无 fallback、凭证仅记录存在性；未输出 Secret，也未验证真实套餐额度。

### 只读 Rights / 费用 / UNKNOWN 观察

- 29 个已存 Creation，引用 25 个 Attempt；保存的 Agent 状态为 225 ok / 12 error，Build 状态为 20 NOT_SUBMITTED / 4 BUILD_COMPLETE / 1 BUILD_FAILED，未见保存的待执行 Agent 或非终态 Build。Gateway 的原结构化请求保留 22 个 RESERVED 和 24 个无 state 记录；RESERVED 是原派发身份留存，不能据此认定仍运行或已经结算，未进行实时查询。两个 @4 Creation 分别为 needs_evidence / failed，均无 Build；未把既有检查点恢复为生产。
- 引用 Attempt 中 **10 份 COMPLETE 生成结果的 billing 均为 UNKNOWN**，其中同一原生成记录在三个 Attempt 中完整复用，按原文只有 **8 个不同 SHA**。这些数量不是费用总额或收费次数；不重新解释旧业务结果、不合并改写记录、不清零 UNKNOWN、不补 request 身份或重派。原首片 @3 Creation 的 7 Attempt、24/24 Preparation 计数保持，不回放。
- 被引用工作区中 368 个 asset 快照的保存 Rights 为 344 KNOWN / 23 ATTRIBUTION_REQUIRED / 1 PUBLIC_DOMAIN。295 个当前可读原件 SHA 与保存值一致；73 个原快照的引用文件在观察位置不可读，保持现场、不恢复或删除。以上只读快照统计**不证明新生产的 Need/Bundle/Rights 准入**。当前两个 @4 Creation 没有生成结果，也没有据此补出 MATERIAL_READY。
- **当前套餐剩余额度、已有 UNKNOWN 占用金额及下一请求最高现金风险未得到可靠证明：BUDGET_NOT_PROVEN。** 历史 ¥10 上限、凭证存在、模型 maxTokens 或 U3-S 的 0 元隔离 CI 报价均不能替代当前权益/现金证据。无新增费用请求，未将 UNKNOWN 当零；本轮未新增生产授权。

### 保全与交接

证据目录 `/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u4-readonly-pgdqiqu1/`：`u4-preflight.json`、`start.json`、原 GET 响应、`loaded-version-audit.json`、dist 比较、安装身份/Skill pin、脱敏 Runtime 配置、Creation/Rights/费用原件索引、Gateway 观察与最终保全检查。没有创建第二套方案或正式审计文档。

**NEXT_SINGLE_ACTION=暂停，等待明确授权受控加载同一 U2 候选；具备页面读取许可及当前费用上限证据后重做 U4。** 本轮不部署/重启、不进入 U5–U6。U2 软件候选与 U3-S PASS 保持，U4 不放行，真实 Web E2E / DEBUG PROGRESS / RELEASE PASS 均无新结果。最终候选、历史原件和文档范围核验结果附于本节收尾。

**收尾核验：**HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389` / `easel-studio` 未变；相对本轮起点仅 Task、Current State、本账本三份文件变化，保留 **74 M / 121 D、0 staged / 0 untracked**。U2 manifest SHA `846bb445d7df5fdfd98332b68e4f989f6e07e64d24e14bb1e226c072b5cd6ddc` 及 1,233 项源码/测试/Skill、8 项非敏感配置、5 项隔离 React 文件逐项无漂移；起始 **3,255 个运行 JSON/JSONL SHA 全部未变**。Web/Gateway 的 PID 和启动时间未变。`git diff --check` 通过，本轮新增文档链接可解析；检查同时发现历史 Task 段落已有 30 个本地 fixture 引用不可解析，未恢复或改写这些历史入口，不宣称全篇历史链接通过。实际页面缺证与本地加载差异仍保留 BLOCKED；没有通过新增测试或历史回放替代 U4。最终核验原件见 `final-fingerprint-check.json`。

## 2026-10-12 U3-S 无付费本地连续集成运行证据

**U3-S = PASS / SOFTWARE_INTEGRATION_PASS；U3-L = NOT_STARTED；RELEASE_NOT_AUTHORIZED。** 本轮用户仅授权当前候选的 45～60 秒中文 mixed 本地集成、关键拒绝和冷恢复；不重放历史失败，完成即停。以下是真实本地渲染的软件证据，**不是实时 Provider、真实 Web E2E 或 Release PASS**。主方案 §8.3 允许外部固定回执；内部 Owner、Rights/Readiness、Hypit Build、媒体解码与最终准入均实际执行，没有直接写入 MATERIAL_READY/Quality READY。

### L2 连续链与实际媒体

- 候选：HEAD `ce6fa81739b812ff6bed8115cabd78bdf548e389` / `easel-studio`；U2 manifest SHA `846bb445d7df5fdfd98332b68e4f989f6e07e64d24e14bb1e226c072b5cd6ddc`。源码/测试/Skill 1,233 项、非敏感配置 8 项、隔离 React 产物 5 项保持原指纹；安装 Hypit 0.2.7，使用独立临时 Runtime，仅本地 media/hyperframes、空凭证，不加载/重启生产服务。
- 新的隔离 CI Creation `cr_03b8bc9f10f24975a21625e24eb2e86a` / Attempt `fa_cfc537ec88deaccee172502d48d8c033`；Build `bld_20261012T145221177Z_BFC9CDFB37`，operation `op_1f217db2e2c647b2a82d2b298f9df068`。原五 pin 为 `truth-source-ref@1 / material-observation-delta@1 / easel-script-claim-ledger@3 / quality-review-delta@1 / easel-hypit-source@1`，Planning 保持当前 @7/@9/v3。Proposal @4、Consent @3、完整 SCRIPT、预置 Voice 身份和 frozen Creator/Director/Creative Mode 经现行 Owner 消费。
- 外部确定性边界：Planning/Truth/VLM 固定合法回执；MiniMax Speech 外部回执返回本机 Tingting 实际中文音频，**仅验证身份绑定及现行合同消费，不证明真实 MiniMax 声线或 Provider 授权**；BGM 与视觉本地自建。实际 Whisper 对完整 SCRIPT 转录/计时，实际 AST 对音乐源观察；Audio/Visual SHA、Material Match、Bundle、Readiness 和冻结 Rights 均由现有模块处理。普通人工 Rights 不能替代生成旁白来源的拒绝原件保留。公开 MiniMax 协议页只读取得，原文提取 SHA `90d05ccc1dbf8404cbc40cfb096698ceec2bc894440ac507cd048ecb9a896ae0` 与已批准条款 pin 相同，未修改合同常量或给历史 Attempt 补资格。
- 真实 Hypit Check/Plan/Pricing：7 个请求 / 7 个 no-charge / `groups=[]` / USD 0。成本批准前 submit 实际拒绝，未创建 Build operation。真实付费 AI/Provider/TTS/Build 请求为 0；离线模拟的生成记录、预留和 UNKNOWN 仍保留原身份，不冒充真实结算。
- 成功 Attempt 的真实 Build 只提交一次，成功导出唯一目标 `final.video`。文件：[本地 MP4](/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u3s-fficf06b/ci/outputs/_creations/cr_03b8bc9f10f24975a21625e24eb2e86a/attempts/fa_cfc537ec88deaccee172502d48d8c033/final.mp4)；**SHA256 `07024bb66cb601fb144179598f482b4c06d1c1c2d7330f14e9148043c9c2d070`，1,033,271 bytes；50.000 秒 H.264 1080×1920 + 50.000 秒 AAC 48kHz 双声道**。实际 Export 由当前 `web._execute_creation_delivery` 查唯一目标，未绕过当前委托资格。
- Quality 实际采样 100 帧，旁白 87 窗最小相关度 0.997；无 clipping/声音遮蔽缺陷，BGM 末段 45/47/48 秒相关度均 1.0；技术 `defects=[]`。System Quality READY、Final Admission 通过。VLM/人工 Review 是明确 CI 外部回执，APPROVED 只属于内部软件测试，不是人类试听、完整播放或发布批准；Rights 的 `internal_production_only/current_creation_only` 限制保留。Main 实际查看 1/25/49 秒画面，中文字幕/视觉在其适用区间可见，末段实际 BGM 信号保持。

### 关键拒绝与原操作冷恢复

`rejections-cold.log` **14 PASS / 20 deselected，228.05s**：Native 成本、runtime bytes/Plan 漂移、UNKNOWN、三切点导出凭据、委托撤销及 Authoring checkpoint 恢复。`material-rejections.log` **3 PASS / 214 deselected，19.57s**：Voice 授权撤销、原音频 SHA 和 Rights UNKNOWN。`protocol-rejections.log` **11 PASS，44.00s**：当前 New-Only 旧主动入口、未准入素材/运行身份及合法停止后的取消边界。没有推断整套 Material 新结果，也没有迁移或删除旧失败测试。

真实 Build 回执在外部边界注入丢失后，Attempt 为 SUBMISSION_UNCERTAIN，重复 submit 返回原 operation 的 idempotent replay、未再 Build。独立新 Python 进程按相同工作区/operation/运行证据认领原 Build；结果入库前保持 unresolved、`retry_allowed=false`。导出后另一个新进程禁止质量 executor，重读保存 Quality、五 pin 和同一实际媒体 SHA，再次通过 Final Admission。`run-18.log` 连续链检查点接续 **1 PASS，16.39s**，不是首次整条运行耗时；`cold-final.log` 独立最终重读 PASS。

本轮失败原件未删除：第一份独立 CI Build `bld_20261012T144915414Z_4249EC6352` 为沙箱 `listen EPERM/pgrep denied`，原 operation 终态失败、无 MP4；获本地隔离渲染权限后另建本轮 CI Attempt，未恢复历史生产。成功 Build 曾被临时脚本错误请求 Output `final`，真实目标为 `final.video`；只修临时验收脚本，沿原成功 operation 完成实际 Export，不修改 Authoring 或重发 Build。所有临时失败日志保留，不能把失败 Build 算通过。

### L1 原件只读分类与当前边界对应

原作品仍为 Proposal @3；**7 个历史 journal / 15 份原始 reply 的 SHA 逐一核验，未重放、未重新解释旧业务结果或恢复旧生产**。原生产不具备当前 @4 准入，标 `HISTORICAL_READ_ONLY / NON_REPLAYABLE_AS_CURRENT_PRODUCTION`；丢失 B 不伪造回复。完整原件路径、request/reply SHA 和 journal SHA 在本轮 `l1-readonly-classification.json`，分类仅作原件审计。对应当前风险验证如下：

| 原 Attempt / 风险 | 当前应有判定与实测证据 |
|---|---|
| `fa_d31a3e20ab22070d99842241a868f44d` / 动作由静图承接 | REJECT；当前 `test_vnext_tool_schema_matches_frozen_choices_and_existing_modality_rules` 拒绝 image 的 required dynamic_action，不靠静图抹掉来源义务。 |
| `fa_559421cca275b16c490249a4571a509b` / role 超长 | 合法短 role ACCEPT，超长 REJECT，不截断；本轮 `current-contract-probe.json` 当前 Schema/consumer 判定一致。 |
| `fa_da27c309a6428657cbac964b3cff9784` / B 丢失 | 缺结果/终态不释放结果或重派；`test_vnext_full_capture[missing/lost_terminal]`；既有当前 R6 B-000 冷恢复证据见 U2 Task。本轮真实 Build UNKNOWN 同 operation 恢复另证。 |
| `fa_07e8c628b4508ea1815930502943a9ea` / framing | 合法组合保持语义，非法 mode/ratio REJECT；`test_vnext_review_contract_protection[atomic_frame]`。 |
| `fa_8d848d7c2b6dba5dd61b508a9abacc5b` / B 引用对象 | 可证等价 codec 往返；非法字段/引用 REJECT，不猜测改写；`test_vnext_review_contract_protection[xml_codec]`。 |
| `fa_ca09eac4f3afcb40b94a903943565d9d` / A-details 游离字段 | 顶层/Need 未注册字段 REJECT，不移到别处；本轮 `current-contract-probe.json` 正反对照。 |
| `fa_eb89de3f9300c1851378db0455157d40` / tempo 对象包装 | 合法 `[60,90]` ACCEPT，`{item:[60,90]}` REJECT，不擅自规范化；本轮 `current-contract-probe.json` 当前 Schema/consumer 一致。 |

以上具名当前 Planning 集合 `l1-current-boundary.log` **5 PASS，0.87s**，另六项合同探针 PASS。只证明当前风险边界，不把原七次真实 FAIL 改成 PASS；按用户要求没有历史失败执行回放。

### 指纹、证据保全与停点

证据目录 `/private/var/folders/s8/sh775m3d14s259bbqfs3w5b40000gn/T/easel-u3s-fficf06b/` 保留：`test_u3s.py`、各轮日志、`u3s-result.json`、实际 Build/Export/Quality/冷进程回执、`mp4-probe.json`、首中尾 PNG、生成/Voice/音乐观察与公开条款原件、L1 原件映射和 `final-fingerprint-check.json`。编译、Skills 合同、git diff --check PASS。独立只读 Reviewer **CONTINUE**，核验了实际 MP4 SHA、连续链/冷恢复和替身边界；Main 签字 U3-S 软件资格。

既有 3,255 个运行 JSON/JSONL SHA 全部未变，起始 dirty 全部保留；本轮仅修改 Task/Current State/本账本，最终 74 M / 121 D、0 staged / 0 untracked（本账本从本轮起点的 clean 变为 modified）。两份本轮临时 Worker 已关闭；无生产服务部署重启、实时模型/付费 Provider、真实 Web E2E、Git commit/push/reset/clean。**RESULT=COMPLETE（仅 U3-S）；DRIFT=NO_DRIFT；TRANSITION=HOLD。NEXT_SINGLE_ACTION=暂停，等待用户单独授权 U4 无付费只读预检；本轮不进入 U3-L/U4–U6，不自动发布。**

## 2026-10-11 用户调整：允许新Creation，以首条完整MP4为终点

原 `cr_70af2a4443b541998f929541ef9f4b84` 的7个失败Attempt、24/24计数和15份原始回复**保持不变，作为回归与审计证据**。不再要求续跑原作品，也不追加原作品独立8次技术调用。此前为旧作品的+8特殊恢复写入但未验证的四文件变更已精确撤回，原先13个tracked修改保留；针对性Python编译和恢复专项8 PASS再次通过。当前 **E1 = FAIL/BLOCKED，未有MP4**，此记录不声称已真实复跑。

新恢复流程：对已有失败按共同原因分组 → 原始响应离线重放定位可通用的接口/合同/程序问题 → 一次系统性修正及失败/成功路径跨阶段集成验证 → 确认Web/Gateway实际加载的冻结版本 → 通过 Easel Web **新建一条 Creation**，从内容确认跑到Planning/Truth、Material/Rights、Native Authoring/Hypit Build/Export/Quality/人工 Review。任何新失败先核对同类回归覆盖，不盲目添加单例Prompt或叠加技术额度。每个阶段仍按PASS/FAIL/BLOCKED/NOT_TESTED留证。

所有新旧Creation的本轮新增现金支出共享原 **¥10** 总上限；不能证明套餐权益或单次最高现金风险则停止新增扣费调用。不扩大到E2/E3、充值、自动付费回退或公开发布。原文下方2026-10-11 13:30暂停记录仍是真实历史状态；后续任何新Web作品须另记 ID、模型/素材调用、费用、Rights、Build/MP4 SHA。



### 本次跨阶段离线验证及当前阻塞（2026-10-11）

- **Preparation/Structured Result：129 PASS**（`tests/test_creation_preparation.py` + `tests/test_openclaw_structured_result.py`）；Planning 当前格式/捕获 **26 PASS**；Material P0本地 E2E **3 PASS**；Native Authoring **16 PASS**；Native Export/人工Review准入专项 **2 PASS**。这些属于分段及内部模拟验证，不应求和宣称全链E2E。
- **完整 Planning 单套：TIMEOUT/NOT PASS**（`tests/test_semantic_planning.py`，600 秒，上次输出至78%）；不要将未完成回归计为通过。UI lint **0 errors/1既有warning**、Vite/TS构建和Python编译及`git diff --check`通过。
- **跨阶段Creator集成测试：FAIL**（`test_same_creator_mode_three_contents_reach_reviewable_first_cut`）。老夹具最初只识别退役的Script Truth回复；临时更换为现行 `truth-source-ref@1` 后能推进到 Material，但仍以旧观察结果模拟，进入 `observe_material` 后未产生合法当前 `material-observation-delta@1` receipts；临时模拟迁移尝试出现 `Material result evidence is missing or changed`，无法证明成功。**全部未通过的临时夹具改动已撤回**，未放宽真实Material/Rights门禁。新集成测试需用当前五pin的真正Owner+合法固定外部响应，完成从同一新Creation到导出/审片的连续状态验证。
- **真实Web：NOT_RUN**。本次已核Easel首页 HTTP 200，但浏览器控制入口未获得可执行准入，因而没有真实新建Creation、MiniMax文字提交、Provider素材生成或Hypit Build；不声称Web E2E通过。仅有上一轮真实作品/Attempt的失败证据。
- **阻塞类别：** `SYSTEMIC_PLANNING_RELIABILITY_UNPROVEN` + `FULL_CHAIN_CURRENT_PROTOCOL_REPLAY_FAIL` + `WEB_E2E_EXECUTION_UNAVAILABLE`；账户权益/供应商实时最高现金风险仍需E0准入，¥10是共享累计新增现金上限而非自动付款许可。下一次真实新作品的前提是当前协议的连续集成回归和Web执行通道均通过，否则停止而不是再加一个Prompt版本。

## 2026-10-11 持续通关 V2（取代 V1 四 Gate 执行顺序；历史记录原样保留）

**同一个任务，两种不同的成功：**调试 E2E 允许故障归类、修复及在身份/版本合法时从持久检查点恢复，只记工程进展；最终 E1 PASS 必须是冻结版本、独立全新 Creation 从 Easel Web 全程生产的真实 MP4（中文旁白+BGM、合法 Rights、Build/文件 SHA、Quality 和人工 Review）。本文件是唯一 E2E 执行/证据账本；Task 定义授权/范围，Current State 汇总状态，Roadmap 定执行顺序。不得把模拟集成测试或跨版本各段 PASS 拼成最终通过。

### 1. 审计后的关键优化

- **收窄旧 Gate A：**现有三内容回放的失败首先属于“待分类的旧 fixture/现行协议不兼容”，不能直接推断是全链产品 Bug；先从中选一个符合现行 Creative Mode、包含 required 视觉/旁白/BGM 的代表作品建立最薄连续集成（不是降低合同）。只替代付费模型/Provider 等不可控外部边界；内部 Owner、Material/Rights/Readiness、Hypit Native/Review 走真实实现。须含真实合法正例、关键非法拒绝例和断点冷恢复；历史三内容夹具全面迁移与 600 秒慢套件不作为首片全部前置，也不能通过 skip 旧测伪造新链成功。
- **P0-A 与 P0-B 并行：**不要先花几小时修夹具、才发现 Web 无法输入。WebCodex 工具不能控制浏览器应记 TOOL_ACCESS_BLOCKED，不是产品 WEB_UI_FAIL。可由用户在真正 Easel Web 页面执行业务点击并以界面状态/真实请求及产物取证；不能通过 API/CLI/数据库伪装 Web。HTTP 200 仅代表存活，必须核对实际表单输入、保存、确认结果。Provider/套餐/成本/权利证据不能等到付费提交后才查。
- **严格区分 Debug 与 Release：**调试阶段可以用版本化本地代码补好问题、合法恢复已有 checkpoint；每次变更保留原件和指纹，跨版本阶段成功只记“找到并突破了一个关口”。收敛后需要一个新 Creation、一个冻结并核对已加载的版本完整跑通，不能靠旧成功阶段拼接。
- **不要求先完成所有质量治理：**E2 的三个新主题、正式 Planning 6/6、耗时/质量优化均放在首片之后。优先确保一条符合冻结业务规格、Right/费用合法、能完整审阅的真实视频，不人为把 required Need 降为 optional，也不强制调用没有费用上界的 H3。

### 2. 执行矩阵（先完成 P0 关键准入，再逐个真实业务关口）

| 工作包 | 允许动作 | 出口标准与证据 |
|---|---|---|
| **P0-A：单作品薄切片** | 真实内部 Creation→Preparation→Planning/Truth→Material/Rights/MATERIAL_READY→Native Authoring→Hypit 本地 Check/Export→Quality/Review，使用一组合法固定外部响应，当前五项 pin 均可用。先查现有旧三内容 fixture，再复用高价值测试，避免新建重复测试体系。 | 一条内部连续成功路径 + 关键合同拒绝 + UNKNOWN 对账/冷恢复；记录模拟边界与版本，标 SOFTWARE_INTEGRATION_PASS 而非 E1 PASS。若现有老测试是测试债，明确标注，不用跳过它替代新证据。 |
| **P0-B：Web/运行/费用准入** | 与 A 并行，无需付费；实际验证 Web 页面操作路径和内容确认，核对 Web/Gateway/OpenClaw/Hypit 源码/配置及加载身份、Creator/Mode、MiniMax 身份/权益、Material Provider Rights、Hypit/素材单请求可能的最大现金风险、未结算操作。 | 产品 UI 可用/工具控制可用分别记账；保存相关源码和运行件 SHA、版本差异、调用/现金/权益/授权证据。Rights UNKNOWN 或费用上界不明仅阻止对应外部调用，不阻止离线修复。 |
| **P1：真实 Web Debug Run** | P0 的对应安全/合同条件满足后，选择一个合法、易观察但非玩具的 45–60 秒、9:16 中文旁白+BGM 主题，通过 Easel Web 新建 Creation，逐关执行 Planning/Truth→Material→Native Authoring→Hypit Build/Export→Review。一个真实回访只检验一个已修复错误家族；费用/调用预算和 UNKNOWN 状态仍逐调用核对。 | 每阶段状态 PASS/FAIL/BLOCKED/NOT_TESTED，Creation/Attempt、原始 SHA、请求/operation key、模型/素材账、Rights、Build/媒体证据。合法检查点允许 Debug 恢复；不得借新 Creation 清空旧账或跳过页面。 |
| **P2：通用根因闭环** | 当前最早失败关口：先保全完整原件、运行身份与远端执行状态，再定位真正 Owner，只修这一个通用故障类；用原始失败重放 + 合法正例 + 非法反例 + 关键跨阶段集成验证，确认实际加载新 fingerprint 后才继续有界真实调用。 | 错误家族 ID、真实失败原件/版本、根因、修复范围、可复验正反结果和未受损合同。不能靠一个新 Prompt 条款、吞掉 schema/语义拒绝、增加技术上限而直接判 FIXED。 |
| **P3：冻结版 Release E2E** | 工程缺陷修复收敛后，冻结源文件、协议、配置、运行安装件和 Web/Gateway/Hypit 实际加载摘要，创建独立全新 Creation，用普通 Easel Web 完整出片。禁止工程师修改已运行的代码/素材/数据库凑结果；合法 Creator 审批不算工程救火。 | 新作品的全部关口在同一 fingerprint 下真实通过：MP4 可播放与音轨、Rights、资金、Build ID 和输出 SHA、Quality、人工 Review。此时记 E1=PASS；后续 E2/E3 另行授权。 |

### P0-A 两项强制出口（从旧交接基线恢复的关键保障，不新增大规模前置）

**L1 历史七次真实 Planning 失败必须逐项处理，不是逐项放宽通过：**为 7 个 Attempt、15 份原始捕获建立一份紧凑的证据映射与原件回归（可复用本文件现有原件引用和既有测试，不另建平行表/Task）。逐项覆盖：`required dynamic_action` 被静图承接、role 超长、B 调用丢失、framing mode/ratio、B 引用对象形态、A-details 游离字段、BGM `tempo_bpm` 对象包装。记录原件 SHA/请求版本、责任层、预期行为（有界接受、可证语义等价 Normalize、局部修复、拒绝或 UNKNOWN 原操作对账）以及**真实回放或明确不可回放的证据**。不存在原始回复的外部异常只允许标 `NON_REPLAYABLE`，以固定故障注入验证责任边界，不能伪装成旧原文已经恢复。完成标准是七类风险都有正确且可重验的判定，**不是七份非法输出被全部接受**；历史真实 FAIL 不改写。

**L2 当前五 pin 的单作品本地真 MP4 必须产出：**固定合法模型/Provider 响应仅作为外部替身，真实内部 Creation/Planning/Truth/Material/Rights/MATERIAL_READY/Native Authoring 处理后，调用已安装 Hypit 的**本地 Check→Build→Export**；检查真实 MP4 非空、SHA、视频流、中文旁白音轨与 BGM 混音结果，并经过正式 Quality/Review。不得 Mock 渲染/导出、跳过 Rights 或直接写 READY。复用现有 `replay_vnext_native_hypit` 的本地能力但必须证明它对当前五 pin 真实连通；旧三主题测试全量迁移仍不作为首片前置。无本地真实 Build 时只能标 `L2=BLOCKED`，不能把 Check/模拟 Export 认作内部全链 PASS。

**进入 P1 的判断：**L1 七项有完成的处理/拒绝/不可回放证据，L2 至少一条代表作品真实本地 Hypit MP4/Review，P0-B 真实 Web UI/加载版本/模型 Rights 与逐调用预算准入成立。以上不要求做 32 次模型 Eval 或三主题稳定性；P1 首次真实模型调用才开始测结构接收率、语义通过情况、合法局部修复次数、总调用成本。若 P1 产生新类型错误，则按相同原件回归闭环补齐，而不是扩张 Prompt。
### P0-B 补充：Web 入口旧协议清理与准入证据（2026-10-11）

**原因：**ADR-005 完成的软件结果协议清理未覆盖全部 Web UI 与 Web API 生产入口。只清理 `Material/Truth/Quality` Writer 后，旧 `legacyDelivery` 前端自动恢复及独立 Authoring/Build/Export 按钮仍可触发与唯一 Delivery Owner 并行的生产路径；`web/app.py` 的聊天确认、Script Truth 审阅还留有非 managed → 旧 Preparation → 手工 Authoring 回退。**上述旧执行路径已按新作品唯一主线进行源码级切断，不仅仅是隐藏按钮。**

- **Web 前端：**`web/frontend/src/components/FilmOperatorPage.tsx` 的旧自动轮询/核价/导出、Provider 直接生成及高级面板手动调度按钮已删除；新作品主操作只在 managed Delivery 上出现，历史 Attempt 的高级面板改为只读证据。原明确的方案确认、必要人工 Truth/Material Rights/Match、费用确认、Quality/Review/最终选片仍在正规 Owner 下保留。`web/frontend/src/lib/api.ts` 的无人使用旧分阶段客户端操作函数已删除。
- **Web 服务端：**`web/app.py` 中旧 Handoff/Attempt、Authoring、Runtime/Check/Pricing/Build/Refresh/Reconcile/Export、MiniMax 直接素材生产的手动 POST 统一以 `410 Gone` 拒绝。正常确认只接受 `easel-creation-delivery@1`；旧 chat Preparation、Script Truth 后重启旧生产链均拒绝或只读。历史 GET 和已存在的原始运行证据保留，不删除或升级旧 Attempt；用户成本批准与显式人工复核仍可进行。
- **回归范围：**新增 `tests/test_web_newonly_routes.py` 测试旧 POST 拒绝、历史 GET 只读、旧 Chat 回退阻断、人工成本批准；旧的 `tests/test_creation_preparation.py` 相应断言迁移到“旧 Web 不再执行”。前端构建/lint 可证本地 JSX/类型有效；无完整浏览器控件实际点击时不得宣称 Web UI E2E PASS；正式服务进程若未重启并核验 SHA，不得宣称已加载修复。
- **验收界线：**本次只处理 Web 入口单线化，不表示 L1 七类真实 Planning 故障、L2 本地 Hypit MP4、P1 实时模型或 P3 真实成片已通过。旧 7 Attempt、24/24、15 Captures、Rights 与 ≤¥10 本轮现金账均保持不变，不主动部署触发付费工作。

### 3. 一个失败的处理决策（最多有界真实回访，禁止循环补丁）

1. **先检查远端是否已执行，绝不直接重试。** 保存最早失败关口、run/tool 原始回执 SHA、创建/尝试/操作 identity、协议与模型路由、Prompt revision、Gateway/Runtime 实际加载、费用/额度。PENDING/SUBMITTING/UNKNOWN 只能沿原 operation 观察/对账；不因重启、更换 Creation 或模型而重派。
2. **归类且区分测试债：**TEST_FIXTURE_STALE、EASEL_CONTRACT、WIRE_REPRESENTATION、MODEL_SEMANTIC、TRANSPORT_RUNTIME、MATERIAL_RIGHTS、HYPIT_BUILD、WEB_UI、COST_QUOTA。故障家族需包含责任层、阶段、字段/合同、原始证据；不同根因不混计。旧 fixture 问题不要改产品合同迎合它，生产 Bug 也不靠改 mock 掩盖。
3. **只修一类系统原因。** 纯机械表示仅在能证明保留语义、来源、许可、数量的情况下版本化 Normalize，保留 raw、派生 receipt；语义未覆盖/required 与 optional 冲突必须交已有 Owner 有界重新判断；Rights/来源/价格/身份不允许猜造。回归至少覆盖原始失败、合法成功和不应被接受的错误。
4. **修复后检查受影响完整链路。** 软件集成可使用合法固定外部响应，但真实内部 Owner 不可模拟直接 READY；测试 TIMEOUT 记 TIMEOUT，不可记 PASS。无需每次跑过所有历史慢测；真正影响到的生产合同/集成测试必须通过。重新核对工作区与实际运行指纹，才派一次新的真实诊断请求。
5. **熔断与暂停。** 同根因两次针对性修复仍失败→Main + 独立 Reviewer 复核问题所属边界、两个修复为何无效、下一个可离线证伪的假设，停止新增计额/付费请求；连续两轮真实诊断没有新业务关口、也没有被正反验证的通用缺陷收敛→暂停反复试跑，输出准确 BLOCKED 和唯一下一动作。出现未知账单、Rights UNKNOWN/RESTRICTED、未知 Build 状态、版本与证据不一致直接安全停止，不得更改合同绕过。

### 4. 衡量进度与跨窗口唯一检查点

- **业务最远关口**（只能用实际 Web + 同一 Creation/fingerprint 认领）：方案正式确认 → Planning/Truth → MATERIAL_READY（MaterialRequirement→ResolutionResult→BindingResult，业务合同不变）→ Native Authoring/Check → Hypit Build/Export → Quality/人工 Review。离线模拟进度独立标 SOFTWARE，绝不混入真实前沿。
- **缺陷燃尽**：实际故障家族的首次/复发次数、能否原件离线复现、是否有合法+非法回归，修复后是否在新版再次出现。Prompt 版本增长、Attempt/测试数量或 API 200 都不是通关。
- **成本与工程干预**：分别记录文字模型、素材、TTS、Hypit 请求次数、技术额度 used/limit、已发生现金、UNKNOWN/待结算、下一请求最大可证明现金风险、Creator 正常业务确认次数和工程手工修改次数。所有本轮新旧 Creation 新增现金共用 ≤¥10；旧原作品 7 Attempt、24/24、15 原件只读保留，新作品自身业务额度不得重置旧账。

每次执行后**只在本文件顶部**更新：RELEASE（HEAD+相关源码 diff/file hashes + 实际 Web/Gateway/Runtime 版本）、RUN（Debug/Release、Creation/Attempt）、REAL_FRONTIER、SOFTWARE_GATE、ERROR_FAMILY（Owner+证据）、FIX_AND_REPLAY（正反与跨阶段）、COST/RIGHTS/UNKNOWN、NEXT_SINGLE_ACTION。跨窗口先检查已有 Job/任务与 dirty diff；多个 Scout 可只读调查，但共享工作区只有一个 Main 具有写入责任。

**现阶段准确入口：**原三内容集成仍因旧 Truth/Material fixture FAIL，Planning 整套 TIMEOUT；新作品真实 Web 尚未执行；WebCodex 工具控制受阻需要与产品页面能力分别核实。下轮先执行 P0-A 当前五 pin 单作品薄切片，P0-B 并行无付费验证页面、运行版本、Rights 与费用。两个关键准入不足时不启动新的模型/媒体/Hypit 有价提交。

> **唯一归属：**[自主首版 Task](../tasks/creator-autonomous-first-cut-2026-09-30.md)；本文件合并用户 E0–E3 长方案与此前 S0–S3 Web 实操，不建立第二套 Task、Agent、状态机或生产链。历史证据不清理，当前状态见 [Current State](../02_CURRENT_STATE.md)。

## 2026-10-11 13:30 恢复验收记录（覆盖下方历史阶段结论）

**实际总状态：E1-S1 方案与 Preparation/Handoff 已真实通过；Planning = FAIL/BLOCKED；E1-S2 MATERIAL_READY、E1-S3 Hypit Build/Export/Quality/Review = NOT_TESTED。** 页面入口是 Easel Web，原 Creation 为 `cr_70af2a4443b541998f929541ef9f4b84`，已确认的片长 50 秒、9:16、简体中文、旁白+BGM；Creator「个人经营实践」、Creative Mode「清醒备忘录 · 视频 · v1.3」。没有新建另一个 Creation 或通过 CLI/API 跳过页面制作。

**真实运行核对（对账后不重试）：** 原 Creation 的 7 个 Attempt 均已冻结原件；Preparation 模型调用共享技术额度 `used=24/limit=24`（累计 24 次，22 次 `ok`、2 次 `error`），已用尽。最新 `fa_eb89de3f9300c1851378db0455157d40` 停在 `preparation=FAILED`、`delivery=failed`、`exhausted_operation=...:prepare`；根因仍是 Planning A/B 的模型结构或语义合同不合格，而不是素材供应商或 Hypit Build 故障。未出现本轮未结算 `pending/submitting/unknown` agent 调用；素材生成记录数 0、Build 提交数 0、MP4 产物 0，不能据此推断文字套餐实际现金扣款为零。

**七次原始证据：** 各 Attempt 的 `materials/recoveries/semantic-planning-vnext.json` 保留；本轮只读核验 7 份 journal、15 份原始模型捕获的 SHA 均匹配，无改写或清理。失败形态按顺序涉及静态图 required dynamic_action / 源义务；候选 role 超长；B 调用丢失；`framing` 非法组合；B 引用对象形态不合格；A-details 顶层散落字段；最后一次 @10 BGM `sound.tempo_bpm={"item":[60,90]}`（正式合同要求长度 2 的整数数组）。最新新请求版本 @11 已加“无明确 BPM 则省略，否则 `[60,90]`”的提示；旧 @10 A-details 提示 SHA 离线复核与原始 `request_sha256` 精确一致，新 @11 提示只做了新的有界说明，但**还没有新的真实模型调用或完成 Planning 证据**。

**代码/测试：** Git 基线 `615974e2a94bed80a3840ea9f7c9aabe602850b5`（本地与远程相同）；现有 13 个 tracked 修改在工作区、未提交/推送，包含 Web 恢复/确认预算修复、Planning 版本化提示、方案修订隔离及对应测试。专项测试 `tests/test_semantic_planning.py -k "versioned_review_batches or frozen_intake or new_b_quote_wire or vnext_query_fault"` = 6 PASS；`tests/test_creation_preparation.py -k "reopen or revision or failed_planning or preparing or budget"` = 8 PASS；`tests/test_creation_preparation.py tests/test_openclaw_structured_result.py` = 129 PASS；慢用例单独隔离 = 1 PASS；前端 oxlint 0 error（现有 1 warning）、TypeScript/Vite build PASS；`git diff --check` PASS。大范围 Planning 回归分别在 240s、110s 截止而**非整套 PASS**。`@11` 的提示修复仅离线验证，不声称模型真正改善。

**当前暂停门禁：** `PREPARE_CALL_LIMIT_EXHAUSTED`。¥10 新增现金授权仍有效，但属于货币边界，**不能自动替换独立的 24 次技术调用上限**。不得因用户说“继续”就清零 `call_budgets`、重新发送旧 Planning Request/UNKNOWN、改变历史 Attempt、创建第 8 个 Attempt 冒充已完成验收，或直接调用 Hypit 制片。本轮所有新增真实文本/媒体请求均已停止。只有在明确批准“为此原 Creation 在保留已用24次的前提下追加多少次模型调用”、并确认新增代码的业务/技术准入后，才可以使用 Easel Web 原「修改方案后继续」入口逐关口执行；新模型请求应保留新的操作键和原失败证据。若无需继续额外调用，可保持 FAIL/BLOCKED 并复盘，绝不虚报首片出片。

## 1. 最小执行方案

**目标：** 一位 Creator、一个现有 Director / Creative Mode、一个新主题，通过 **Easel Web `http://127.0.0.1:7860`** 产生真实可播放、可在 Easel 内审阅的 MP4。禁止以直调 Python、OpenClaw API、Hypit CLI Build 或改数据库凑出“Web E2E PASS”。

| 阶段 | 业务动作（都在 Easel Web） | 判定 |
|---|---|---|
| **E0 只读准入** | 版本、Web/Gateway、固定 Creator/Mode、Model/Provider/Right/费用及旧 PENDING/SUBMITTING/UNKNOWN 检查，不建新 Creation，不发模型请求 | 版本对齐且每个实际扣费请求的可证明最高新增现金风险在 ¥10 剩余额度内；否则停在明确阻塞 |
| **E1-S1 创作方案** | 新对话输入主题，讨论剧本/分镜/声音，Easel 正式确认，创建本轮唯一新 Creation/Attempt，真实 Planning A/B 和 Truth | 真实语义/原件合同合法、可冻结身份与来源 |
| **E1-S2 真实素材** | 作品页面处理图像、旁白、BGM 的正规来源、Match、Inspector、Rights / Readiness | 所有 required Need 都有合格资产，`MaterialBundle + MaterialReadiness = READY`，optional 缺失不自动阻断 |
| **E1-S3 出片审片** | Easel 原生 Authoring→Hypit Check/Plan/Pricing/批准→Build/Export→Quality→人工审片/选择 | 真实 MP4 可播放、音画齐全、输出 SHA/权限/成本可对账；人工接受与公开发布分开 |
| **E2 稳定性** | 同一冻结版本 3 个新主题、3 条独立 Creation | 3/3、零工程技术救火、零未知收费；**本轮不启动** |
| **E3 质量效率** | 主题、导演一致性、素材、声音、观感、实际现金和各阶段耗时 | 可先以均分 ≥3.5 / 单项 ≥3 作为候选标准，但**未真实审阅就记 NOT_TESTED**；**本轮不启动** |

主题候选：**《AI 时代，一个普通程序员的深夜》**。建议 9:16、45～60 秒、中文旁白与 BGM，人物为虚构，不能宣称 Creator 的真实个人经历。遵从冻结的当前 Mode，不为符合建议规格修改 Director 风格。E1 功能成功（真实片通过技术与内容审阅）与自主成功（无工程手改素材/Run/数据库）分别记账。普通用户方案/权益审批不算“工程救火”。

## 2. 严格按 Web 点击的执行手册

1. **E0：**浏览器访问 `http://127.0.0.1:7860/`，核对“网关已连接”；选择现有“个人经营实践”画像与“清醒备忘录 · 视频 · v1.3”风格；只读核对 Git SHA、Web/Gateway、Hypit、Provider/模型认证与套餐、各类素材可用性、旧的 UNKNOWN/执行中状态，以及现金风险。E0 不发送聊天、不创建 Creation。
2. **E1-S1：**在“对话”→“新对话”输入下面的主题/制作意图。**发送是实际模型请求，必须在 E0 的费用/权限门禁通过之后。**阅读 Easel 正式方案，经现有确认界面确认后，只生成**一个新的** Creation / Attempt，记录冻结内容、Creator/Mode 和 Planning/Truth 状态。
3. **E1-S2：**继续该 Creation 自身的视频制作卡片，查看 Need、素材候选、Rights、预览与成本；通过原生页面按钮获取或补足所需图像/声音。每次可能扣费前重新算现金风险。仅当所有 required Need 合格且页面/实际业务证据达到 `MATERIAL_READY` 才继续；Rights UNKNOWN / RESTRICTED 不能绕过。
4. **E1-S3：**页面推进 Native Authoring、Hypit Check、Plan/Pricing。**软件里的 USD `approved_budget_usd` 不是支付平台硬上限**；真实新增现金上界已证实后，使用页面原有确认操作最多一次 Build，再通过 Easel 页面 Export、系统 Quality 与人工 Review；保存输出 SHA、MP4 播放/音轨观察、是否入库，不发布。
5. **遇阻即停：**标记 `MODEL / CONTRACT / MATERIAL / AUTHORING / BUILD / RUNTIME / QUALITY`；保留可合法保存的原始模型/Provider 回执、外部 operation key、时间/费用、失败原因。已开始提交但结果 UNKNOWN 先对账，绝不盲目重派；不可通过直接运行内部函数或修改文件让 E2E 伪 PASS。代码/Runtime 实质变更后，旧版本的稳定性数据不得冒充同版 3/3。
6. **判定：**对每一关只记 `PASS / FAIL / BLOCKED / NOT_TESTED`；正常 Creator 批准与工程师手动修复分开计数；记录总墙钟/实际执行/等人确认时间；真实评分不得预填。

**E0 通过后才可发送的 Web 消息示例：**

> 请使用当前“个人经营实践”画像与“清醒备忘录 · 视频 · v1.3” Creative Mode，为主题《AI 时代，一个普通程序员的深夜》策划一条约 45～60 秒、9:16 的中文短视频，有中文旁白和 BGM。人物为虚构，不能声称是我的真实经历。先在 Easel 讨论具体故事、分镜、声音和素材方案，我确认后再启动生产；请保留已冻结的导演风格。只使用本次明确授权的素材和费用，累计新增现金不能超过 ¥10；不能证明费用上界时必须停下，不自动发布。

## 3. ¥10 预算与停止线（不继承旧 ¥30）

用户已授权 **本次 E1 单条新作品新增累计现金支出上限 = 人民币 ¥10.00**，不授权 E2、购买余额、充值、自动套餐升级、付费 fallback 或发布。报价、套餐/积分扣减、真实现金支出分开记录；人民币总支出上界应同时计入已发生、已占用/待结算、下个请求最大可能的现金成本。不能证明上界就 `BUDGET_NOT_PROVEN`，**不触发该外部请求**。USD 额度/估价不是硬限； UNKNOWN 不能记 ¥0；提交不确定先对账，不因为失败重启而清零。合法零新增现金的订阅权益也必须得到当前证据，不根据用户历史猜测。

## 4. 2026-10-10 实际 E0 结果（本轮执行现场）

| 已执行检查 | 实际证据 | 结果 |
|---|---|---|
| Git / Web / Hypit | `easel-studio` 与远程同 SHA `615974e2a94bed80a3840ea9f7c9aabe602850b5`；Gateway、Web 正常运行；Hypit 0.2.7 | PASS（环境基线） |
| **真实 Web UI** | 浏览器打开 `127.0.0.1:7860`，页面显示“网关已连接”；选择画像“个人经营实践”后，Creative Mode 显示“清醒备忘录 · 视频 · v1.3”；未创建 Creation 或发送模型消息 | PASS（E0 页面准备） |
| Core-video 就绪 | 21 项依赖综合 `NOT_READY`；`openclaw.model-auth` / `model-endpoint` = `NOT_VERIFIED`；1 份 Rights sidecar 是结构有效记录，但 `material.visual-source = CONTENT_EMPTY` | BLOCKED（不能直接认领真实制作已准备好） |
| Generation 配置 | 3 项依赖，`READY`，但不等于真实生成/收费/可用权益 | CONFIG_READY |
| 历史 Attempt 只读摘要 | 最多检查 200，实得 20 个 Creation、16 个 Hypit Attempt：11 `NOT_SUBMITTED`、4 `BUILD_COMPLETE`、1 `BUILD_FAILED`；未在这组中找到非终态/未知 Build。历史独立 Planning HTTP UNKNOWN 仍按封存证据保留 | PASS（仅上述样本范围） |
| Provider/现金上界 | 真实模型套餐/认证、新素材路线、Hypit Provider 可能扣费的有效上限，**仍缺可核证据**。不能将目录价或审批金额充当最大支出约束 | **BUDGET_NOT_PROVEN** |
| E1 创建、Planning、素材、Build、MP4 与审片 | E0 支出风险未准入前，没有发起实际模型请求，没有创建新 Creation | **NOT_TESTED** |

**额外 E0 费用核对：** 当前 OpenClaw 隔离配置默认模型为 MiniMax-M3（单次模型输出配置上限 8192 tokens），本地存在相关凭据配置，但这**不证明实际认证或套餐扣费身份**。官方 [MiniMax API 价格表](https://platform.minimax.io/docs/pricing/overview)公布 M3 令牌计价、image-01、TTS 和 H3 视频的公开目录价；这些不是当前账户的现金硬上限。尝试通过官方只读套餐余量入口核验当前密钥时出现网络 `URLError`，**没有取得账户权益/现金上限凭据**。首条优先评估具备实际 Rights 的免费 stock 或已批准素材；不要在未证明限额时触发按秒收费的 H3 视频生成，也不要因先前目录价很低而默认放行自动多轮模型调用。

**本轮统一结论：`E0 = BLOCKED_FOR_PAID_EXECUTION`，`E1 = NOT_TESTED`。** 此处停止的是**有现金风险的真实外部提交**，而不是倒退重新做 ADR-005 或 Planning 架构。下一动作只核实模型套餐的当前增量现金权益及素材/Build 可证明的上界；满足¥10和现有业务准入后，再在此方案下从一个新 Creation 继续。此 E0 结论不能冒充真实 MP4 E2E PASS，历史费用、FAIL/UNKNOWN 与预算原件未改。

## 5. 最新 E1-S1 真实 Easel Web 执行进度（2026-10-10，后续授权）

用户随后明确表示已购买 MiniMax 套餐，并授权先通过 Easel Web 使用模型；继续遵守单条 E1 新增现金预算 ¥10，不充值、不自动切换按量或发起无上界的媒体费用。本节**覆盖前述 E0 阻塞时点的“没有请求/未创建”历史状态**，不是重写早前检查记录。

- 已在 Easel Web 的同一对话中真实发送主题《AI 时代，一个普通程序员的深夜》及两轮补齐/规格整理要求，收到模型回应；自动建立单个 Creation `cr_70af2a4443b541998f929541ef9f4b84`，选定既有「个人经营实践」和「清醒备忘录 · 视频 · v1.3」。使用 Web 页面选择 50 秒、9:16、旁白与音乐、简体中文；最初回复因没有将纯旁白代码块与镜头说明分开，被正式方案解析拒绝。通过**同一 Web 对话**输出五个严格章节后，后端方案达到 `READY_FOR_CONFIRMATION`，有 `easel-video-proposal@3` 及有效 SHA，未新建第二 Creation。
- 正式点击「按这个方案制作」后，页面两次显示业务校验错误「已确认旁白缺少对应的技术身份和预算授权」。只读核实作品仍在 `PROPOSAL`、`confirmed_at` 为空、`delivery` 未创建、`Attempt` 数量 0。缺口是 v3 确认时预置旁白技术身份须随合法的素材生成授权一起写入，未触发 Planning、Provider 素材生成、Hypit Build 或 Export。不存在可以冒认的成功出片。
- 尝试通过 WebCodex 浏览器 UI 的 `set_value(10)` 写入页面的「本次自主素材生成总预算（人民币）」控件，但截图证实页面仍为空、React 控件值未实际保存；重复确认会得到相同拒绝，**已停止重复点击**。这是本次浏览器操作入口与页面控件的实际阻塞，不允许通过 Python 直接确认 Creation、写数据库或 API POST 绕过 Web。
- **最新状态：`E1-S1 = BLOCKED_AT_WEB_CONFIRMATION`，`E1-S2/S3 = NOT_TESTED`。** 下一操作仅需在 Easel Web 现有作品右侧把「本次自主素材生成总预算」实际输入 `10` 元，肉眼确认输入框显示 10，再点击「按这个方案制作」一次，并按 UI 的 Rights/文字使用范围及费用提示确认。完成后继续读取同一 Creation 的阶段投影和预算状态；不重发模型消息、不新建 Attempt、不购买额外套餐。
- 本轮有真实订阅模型交互，**未查询到可靠的账户现金扣款明细**，因此不得以模型回复成功冒称新增现金一定为 0 元；已知本轮没有主动执行媒体生成或 Hypit Build。
