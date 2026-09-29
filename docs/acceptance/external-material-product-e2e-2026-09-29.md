# External Material Product E2E — 2026-09-29

状态：**REAL_WORLD_VERIFIED / PASS（仅到 MaterialReadiness）**。

## 范围与身份

- 标准 `ai-film` 对话会话从主题提案开始，结构化 `confirm_production` 确认方案；Creation `cr_fc46c0fd949a4beca0043be745b9458d`，Attempt `fa_c1e6b95191ce6b69be351d8a39cb1e81`。
- 方案：10 秒、9:16、静音、固定机位森林晨光、屏幕文字“停一下。”；只需一个 required 外部视频 Need，不使用 Local 或 AI 生成，不发布。
- Preparation 冻结 Content Core、Truth Packet、Creator Context 和 Production Brief。Planning 自然产生 `plan-6b69be351d8a39cb1e81`、SCRIPT、SCENES、TREATMENT 和 `need-video-forest-dawn-still-cam-01`；没有手工创建或修改 Plan、Need、Asset、Bundle。
- Script Truth 经正式 Operator API 以 `codex_delegate` 审阅并通过，SCRIPT SHA `187299b1da644346fd6a0f913061d4ee55acde76a7ac2ddde6bbd7bc2ed1062e`，Truth Packet SHA `8a75da8c45bb1e31d37612d080fcd0e1735b37bb817fce27832a26914a53c82a`。Truth Packet 无事实 claims；44 条审阅项为制作说明、画面文字和排除规则。

## 真实供应证据

- SourceRouter 尝试 Local、Pexels、Pixabay。Local 无候选；Pixabay 视频搜索报告 `UNSUPPORTED`；Pexels 返回 20 个真实候选，正式 ProductMaterialSupply 获取其中 3 个视频。没有使用发现型 Provider 假装 Acquisition。
- Acquisition 为 `provider_direct_url`；三个资产均有 Pexels 资产页、作者、获取记录、字节 SHA 和技术检查 `PASSED`。排名第一的 Pexels `4235317` 对应 Asset `asset-9636baf66b2746089e0f20e294dc3614`，SHA `22759f9c0ea290eeba8f16b0849a0622543f2aa2d312095ea6d38ad90468ce5d`，960×540、21.205 秒、H.264 视频。素材页：<https://www.pexels.com/video/video-of-foggy-forest-4235317/>。
- Asset Rights 记录包含资产级 Provider listing 和 Pexels License 条款映射，许可证 URL <https://www.pexels.com/license/>，以及使用限制。RightsService 对排名第一资产返回 `ADMITTED / evidence_and_usage_constraints_compatible`；无人工覆盖或捏造权利事实。其余两个资产亦为 `ADMITTED`。
- Match 的硬约束 `passed`，Bundle `bundle-6b69be351d8a39cb1e81` 修订 `b67e82853b1451400824a65d130dda1a58474551b47fe8870b334b7ee193d8d4`，required Need 覆盖数 1/1。按当前 Plan、Bundle、真实字节重新计算的 MaterialReadiness 为 `READY`，无 blocking Need。证据位于 Attempt workspace 的 `materials/` 下。
- Codex 操作员查看排名第一视频在 0、5、10、19 秒的画面：固定机位雾林与晨光，抽查帧未见人物、商标或水印；接受该候选满足本次 Need 的画面要求。此项是质量审核，不能替代 Rights、技术或匹配 Gate。

## 阻塞、修复与停止点

- Preparation 首次因 Content Core 内部引号未转义失败，第二次因 topic 将初始主题字符改写失败；通过同一已确认对话重试草稿生成后通过冻结校验，没有直接改状态或写中间素材对象。
- 首轮 Pexels 搜索成功但获取失败：本机 VPN 将素材域解析为 `198.18.x.x` 合成地址，被公网地址校验拒绝。获取层仅对该合成地址段增加 HTTPS DNS 公网解析回退，仍执行 Provider 域名白名单、公网 IP 校验、固定地址连接和 TLS 主机名验证。用同一真实 Plan/Attempt 在产品 Supply 服务重试当前阶段，随后由正式 MaterialGateIntegration 写入 `MATERIAL_READY`；没有手工插入数据库或 Material 对象。
- 停在 MaterialReadiness。Attempt `authoring.status=pending`、`execution_status=NOT_SUBMITTED`、Build `not_submitted`；没有生成 SVML/SVRun，没有调用 Hypit、Build、Export 或 Review。
- 由于在 Gate READY 处按本 Goal 停止，没有调用会继续启动 Authoring 的对话恢复操作；Creation 的 Preparation 摘要仍显示此前的 `MATERIAL_NOT_READY`，而当前 Attempt Gate 和 Readiness 已是 READY。这是产品重试入口/摘要同步的后续问题，不改变本次 Gate 证据。
- 本机直接访问 Pexels 条款网页返回 HTTP 403；本次 Rights 结论来自已记录的正式 Adapter 条款映射、资产页证据及 RightsService Gate，未声称额外的人工网页条款核验。匹配器没有语义分析证据，合格性依赖硬约束、技术检查、Rights 与上述画面抽查。

## 验证

`.venv/bin/python -m pytest -q tests/test_material_acquisition.py tests/test_material_integration.py tests/test_material_readiness.py tests/test_pexels_provider.py`：62 passed；相关文件 compileall 与 `git diff --check` 通过。以上测试均未调用付费 AI 或真实 Provider；真实 Provider 调用只发生在具名 E2E 操作中。
