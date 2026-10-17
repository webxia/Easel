# S6-15 · G4 最终合同审查与准入决定

**2026-10-17｜G4_REVIEW_COMPLETED / NO_GO（准入未通过）**。本轮已经完成 G4 所要求的上下游回查、五模态证据对照和准入决定；这**不等于 G4 PASS**。仍有 G3 真实素材下载和质量缺口，**S6-14 继续 REAL_PRODUCTION_PAUSED**。用户要求本轮工作完成后暂停，禁止自动进入真实制作、迁移、发布或合并。

## 1. 范围与事实基线

- 活动工作树：/Users/xgx/.codex/worktrees/s5-architecture/Easel；分支 codex/s6-production；审查起点 HEAD 5cb4a01de325cf0ab687aafe35892ad07d22263d。最终审查补丁的提交及 CI 精确 SHA 参见 [PR #8](https://github.com/webxia/Easel/pull/8)。
- 正式依据：[需求](01_REQUIREMENTS.md) / [职责](02_ARCHITECTURE.md) / [唯一可执行合同](15_IMPLEMENTATION_DESIGN.md) / [G0](17_MATERIAL_LAYER_AUDIT.md) / [G1](18_MATERIAL_LAYER_ARCHITECTURE.md) / [S6-15](tasks/S6-15_material-layer-hardening.md)。
- 五类素材：图片、视频、BGM、固定 AI 旁白、SFX。根据最新决定，Unsplash 仅维持主动预览，**不纳入生产供料验收范围**；不新增音频管理 UI，Freesound 未注册。
- 证据层级：离线合约测试、本地真实 FFmpeg/FFprobe、真实检索 API、合法真实媒体下载、音画语义/试听、Creator 接受，必须分开记录；只验到前几层不得越级声称完整通过。

## 2. 上下游责任、协议和五模态证据

| 检查点 | 输入到输出/关键不变量 | 当前证据 | 判定 |
|---|---|---|---|
| Creator / Director / Planning | 冻结画像、Director、已确认 Plan → MaterialIntent → MaterialNeed；不自改内容、授权与导演权 | 上下文 fingerprint、场景一致、重复恢复及负例软件验证 | 软件 PASS |
| 图片 | 库优先 → Pexels/Pixabay → Rights/文件 → asset_ids → EditProject.scenes | 两家平台真实图片 API 分别返回 3 条；实际下载/入库未通过 | 搜索 PASS、生产未验 |
| 视频 | 同上，保留视频时长、原声、所选素材版本与剪辑引用 | 两家平台真实视频 API 分别返回 3 条；未做真实下载、真实作品 | 搜索 PASS、生产未验 |
| BGM | MaterialNeed(audio,music) → 合格库/来源 → AudioClip(music) | 本地/Mock 音轨、同源重复复用、Rights 与 credits 通过；Commons 真实许可元数据搜索通过 | 软件 PASS、真实未验 |
| SFX | sound_cues 的 cue_id、scene_id、at、duration、required → audio(sfx) → AudioClip(sfx) | 必需阻断、可选省略、双事件共用字节、事件时序检查；Commons 搜索有候选 | 软件 PASS、真实听感未验 |
| 固定 AI 旁白 | scene.narration、固定 VoiceIdentity → Voice Operation → 句段音频 → 音轨/字幕 | 原生 MiniMax T2A JSON/hex、UNKNOWN 不重发、本地模拟及合成媒体测试；本机真实声音配置缺失 | 软件 PASS、真实不可用 |
| 权益/来源 | source、Rights、SHA、许可/署名 → 下载前预查/入库、edit/选中/render 前复验 | 公共 IP/DNS 重定向、Rights/范围、换版 SHA1、防越权负例；真实 CDN 获取被安全拒绝 | 软件 PASS、远端未验 |
| 用途与输出 | 多用途 material_uses、候选与已选资产分离；仅 schema_version / asset_ids → Editor | FFmpeg 五模态合成短片到 reviewable，selected-only、署名依赖/版本检查通过 | 软件 PASS |
| 状态与成本 | work/plan_rev 权威、授权撤销、素材恢复不再下载；有价操作独占 OperationService，UNKNOWN 不重发 | 本地回归与负例通过；未发真实有价调用 | 软件 PASS |
| 不能破坏的公共边界 | Plan、Editor、Operation 不修改、不恢复 V1 双重对外消息协议 | 与 G0 固定 SHA-256 完全一致（下文） | PASS |

**所有权**：导演负责语义选择；素材层负责权限、查找、入库、身份/权益及交付；Operation/Work 管状态和计费；Editor/QC 管剪辑和质量；用户管具体版本接受。库内同 SHA 可以共享物理文件，但不能合并不同 Rights/署名版本；历史 2 条音频逻辑记录是不同署名证据，同一实体，不得为了去重删除旧记录。

## 3. 公共合同 SHA-256（本轮实测与 G0 一致）

- easel/production/contracts.py：40d1ac34faf4d85c9a8b82647fd997340eff9b226ff8cdf68f0c992b732ff66c
- easel/production/editors/base.py：de7815360cee428d70c26e8f437d06843376ed8e5d56728cf17aa3dd48c44cfe
- easel/production/operations.py：63e0767ef5d36b47e735656764d78ae8ac7dd8b1613118aaf4f68a03e6b0d1be

## 4. 本轮实测范围与 CI 缺口

- 本机隔离虚拟环境 python -m pytest -q tests/production：**406 passed、3 skipped**；包含实际 FFmpeg/FFprobe 本地音画 FFmpeg 合成至 reviewable，真实 AI 语义/音色不在这个 PASS 范围。跳过为两个 Windows junction 和一个 900 秒 opt-in。
- 缺 FFprobe 模拟环境下两个针对性用例 **2 passed**；[旧失败 CI @ 5cb4a01d](https://github.com/webxia/Easel/actions/runs/39008831490) Ubuntu 1 fail、Windows 1 fail 均源于 test_audio_supply_downloads_bgm_only_once_and_retains_source_and_credits 把 Rights/复用测试错误耦合真实 FFprobe，返回 technical_inspection_not_passed。本轮**只修改测试**：使用 Python wave 对真实 WAV fixture 解析验证并标明独立测试替身。保留真实 OGG + FFmpeg/FFprobe 端到端用例，不放宽生产技术安全判据。新提交的远端 CI 必须以确切 SHA 检查，不预报通过。
- 之前同源前端测试 80 passed；本轮不修改前端。文档校验与 Git hygiene 见提交验证结果。
- 真实**免费** API 检索：已配置的 Pexels / Pixabay 图片和视频，各返回 **3 条**含来源声明和证据的候选；Commons 官方公开匿名 API 以 rain、piano 检索，各有 **3 条**满足当前 CC0/CC BY 4.0 白名单的音频元数据候选。未发付费模型/生图/生视频/TTS。
- 真实媒体字节下载 NOT_PASSED：本机对 upload.wikimedia.org、images.pexels.com、cdn.pixabay.com 的域名都解析至**非公网地址**；现有 RemoteURLPolicy 的防 SSRF 校验准确拒绝下载，未尝试关闭、伪造公网 IP 或经过绕行通道。不能以能搜索就把 CDN 下载登记为成功。
- 真实语义和自然度未验：本机只有此前的一个唯一 MP3，没有不同题材 BGM/SFX 真实资产试听和导出；EASEL_VOICE_SERVICES_JSON 和实际生成 Rights 均未完成具名配置，有密钥不等于授权；Creator 接受未发生。

## 5. G4 NO_GO 的阻断项与关闭标准

| 编号 | 级别 | 事实 | 真正关闭所需证据 |
|---|---|---|---|
| G4-B1 | P0 | 现有运行网络阻断合法真实 CDN 文件获取（非公网 DNS） | 在允许的真实公网 DNS 网络中，合法图片/视频/BGM/SFX 各取代表性文件，走原有安全下载、Rights、文件摘要、FFprobe、入库与 Editor 消费；**不降低防 SSRF** |
| G4-B2 | P0 | 实际 BGM/SFX 音源覆盖、导演真实听取选择、事件位置和混音效果尚未验证 | 真实合法曲目和音效落入库后，用不同片段/题材验证选中资产、cue 时间、credits 与试听，必要素材不足明确 needs_decision |
| G4-B3 | P0（五模态真实） | AI 旁白的服务/声线及自然度没有真实证据 | 需要明确声线身份、服务权利和单次真实调用授权；先单独通过 Voice 真实试听/时长/句段证据，再用于 S6-14 声音质量验收 |
| G4-B4 | P0（CI 门禁） | 旧精确 SHA 的 Ubuntu/Windows 测试失败；当前本地定向修复尚待新远端 CI | 新开发提交在所需 CI 平台实际运行且全通过；不把本地或旧提交状态冒称最新 CI PASS |
| G4-R1 | 已知兼容差异 | Plan.Scene.id 允许最多 128 字符；Editor.scene_id 最多 96 字符 | 不修改冻结公共合同；后续做明确 ID 映射/边界提案及极值 E2E，当前不可声称任意正式 Plan ID 均可渲染 |
| G4-R2 | 版权与恢复风险 | Commons 文件许可是发布者的声明；基础音乐作品、表演录音、人物/商标等第三方权利不自动获得；断电窗口未全测 | 保留文件页、实际许可版本和素材特定记录；正式应用前再验证；未知操作不得盲目重复提交 |

**最终判据**：G0/G1/G2 + 本地 G3 软件 PASS、外部搜索成功≠G3 真实文件成功。P0 B1～B4 未闭合时 **G4 决策只能 NO_GO，不得批准 S6-14**。


## 2026-10-17 · 新授权：Clash Fake-IP 安全下载修复

用户新指令要求只修复安全代理下载，不执行 S6-14。新增显式 EASEL_MATERIAL_HTTP_PROXY=http://127.0.0.1:7897，仅允许 loopback HTTP CONNECT；通过已验证 TLS 的 Cloudflare 1.1.1.1 HTTPS DoH 查询公网 IP 并校验，然后经代理 CONNECT 到验证过的数字公网 IP:443，继续使用原媒体域名执行 TLS SNI/证书验证。逐跳白名单、非公网地址拒绝、文件大小/MIME/技术核验/Rights 均保持，不读系统环境代理。不配置时原直连方式不变。V2 Git 忽略的 .env（0600）已显式配置，旧项目/历史素材不改。

本次真实下载：Pexels JPEG 481691 字节、MP4 624725 字节/14.531183 秒和 Wikimedia OGG BGM 108207 字节/8.127732 秒均在独立临时素材库验证 Rights ADMITTED、Technical PASSED 和可复用候选 1；Pixabay 图片 JPEG 398639 字节已完成安全代理下载，Pixabay 视频探针超过单次诊断的 15MB 上限；Wikimedia SFX 的 door/water 检索有候选，但 CDN HTTP 429，无实际 SFX 文件。没有调用收费生成服务，没有启动视频制作。此时只证明安全下载通路与部分真实素材的供应资格，缺 SFX 真正下载、作品/音效试听与固定 AI 旁白；因此 G4 原 NO-GO 与 S6-14 暂停不变。对应源码 easel/materials/application/proxy.py，tests/production/test_proxy_material_acquisition.py。## 6. 许可参考、暂停与交接

- [Commons 外部复用](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)及[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)：遵守源文件页许可、创作者署名、如有修改须说明；不可把平台声明当作独立版权保证。
- [Pexels License](https://www.pexels.com/license/)、[Pixabay License](https://pixabay.com/service/license-summary/)：许可通常允许创意合成，但仍需遵守不作独立素材转售、不暗示背书及肖像/商标等限制。
- 只有上述 G4 阻断项获得可核查证据，才能另起一轮正式 G4 准入决定。G4 的审查流程与 NO_GO 决策**已完成**；依用户指令**本轮现在暂停**，不得继续推进 S6-14、发布、迁移或启动后台持续验证。
