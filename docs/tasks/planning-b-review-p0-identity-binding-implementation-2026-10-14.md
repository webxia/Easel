# B Review P0｜显式身份绑定实施分支方案

> **导航说明（2026-10-15）：本文件保留 R02–R08 的实施、失败和原始证据，不再调度下一工程动作。** 当前唯一执行焦点在 [Creator Task](creator-autonomous-first-cut-2026-09-30.md) 下的 [Planning Creative Authority D0–D4 实施方案](planning-creative-authority-implementation-plan-2026-10-15.md)；原先各节 `NEXT_SINGLE_ACTION` 均为其记录时点的历史状态。

> 状态：IMPLEMENTATION_IN_PROGRESS / S0-S2_CODED / S3-S4_PARTIAL / S5_NOT_STARTED / NOT_A_GATE  
> 日期：2026-10-14  
> 本文件仅记录候选实施方案，**不修改主线、不构成实施授权**。New-Only U0–U6 第 8 章、Creator Task、正式合同及历史 Attempt 仍为唯一准入和执行标准。

## 1. 背景与目标

真实 MiniMax M3.1 Planning：
- Low 首个失败 B-001：要求 question-0008～0015；实际只有 0008～0013，缺 0014/0015，且多出根字段 decision、reason、support。
- Medium 首个失败 B-006：要求 question-0048～0055；实际只有 0048～0053，缺 0054/0055。
- 两轮均为 B Review 合同失败，不是 HTTP 失败。每批请求约 179–183 KB（约 5.1–5.3 万输入 Token），不存在批次递增导致无限膨胀的已证实趋势。
- P0 独立 Medium Demo：显式 question_id + answer、修正 Schema 后，两组配对结构验证通过。但交换两个问题的答案能穿透结构和字面引用验证，**语义错绑仍是开放风险**。
- P1 Demo 虽减少约 5.9% 输入 Token，却有个别 quote 不准确；**本方案明确不包含 P1**。

**唯一目的：**降低动态根问题键生成带来的格式错误。程序冻结问题身份，模型显式绑定身份并提供语义判断，之后确定性映射回原始 B 领域合同。不能因这一改造声称解决模型真实漏答或语义错误。

## 2. 范围与不可改动的边界

仅拟改 B Review 的 Tool Schema / wire 输出表示、身份 Decoder、现有执行器接入及测试。保持 A-selection/A-details、Truth、Creator/Director/Creative Mode、Material V1.3、Authoring、Hypit、Rights、冻结原文、B Review 原问题及 8 问批次、领域 Answer、来源和语义判定、共享 Repair 预算、UNKNOWN/PENDING 对账不变。不改全局模型配置、推理等级或上下文裁剪。

## 3. 现有源码与候选改动

| 文件 | 当前责任 | 计划改动 |
|---|---|---|
| `easel/integrations/planning_review_support.py` | B 每题 canonical Schema，动态根问题键 | 增加只供 B 模型使用的显式身份 wire Schema；每个 ID 使用 const 与专属 Answer Schema 精确匹配 |
| `easel/integrations/planning_wire.py` | Schema 投影、解码及严格校验 | 严格身份投影/Decoder，保留原 canonical 合同，不猜测、补齐、纠正模型回答 |
| `easel/integrations/planning_candidate_review.py` | `_wrapper`、`_row`、`decode_answers`、`semantic_targets`、共享跨批 Repair | 继续消费还原后的原 canonical B 结果；原有拒绝规则和修复限额不变 |
| `easel/integrations/semantic_boundary_run.py` | 原始回执、请求和 Schema 身份、断点恢复 | 接入新 B-only wire、保留旧版本只读回放与新的冻结 operation 身份 |
| `easel/integrations/planning_semantic_review.py` | B 问题和完整上下文 | 不改变上下文，仅按必要程度修改输出格式 guidance |

### 3.1 候选 wire 示意

```json
{
  "answers": [
    {
      "question_id": "question-0008",
      "answer": {
        "decision": "ACCEPT",
        "reason": "必须由真实冻结来源支持的模型判断",
        "support": []
      }
    }
  ]
}
```

这只是格式示意，**不是合法的完整审核回执**。生产必须返回本批所有问题的完整答案；ACCEPT 必须维持真实授权来源约束。应使用 `oneOf + const(question_id)` 为每个 question_id 绑定其专属 Answer Schema；禁止复用未绑定 ID 的重叠 oneOf（此前 Demo 自身曾因此错误拒绝）。

### 3.2 严格解码与领域回接

1. 发送前冻结问题注册表、输入、Schema 指纹、模型参数、运行和 operation 身份。
2. 解析返回 JSON，核对 ID 合法性、唯一性、全量覆盖、字段类型与每题专属 Schema。缺失/多余/重复 ID 都拒绝；禁止根据数组位置推断答案归属。
3. 仅按模型显式提供的 question_id 映射回 canonical `{question-xxxx: answer}`，不改写回答内容。再由原 canonical Schema、`_wrapper`、`_row`、`decode_answers`、`semantic_targets` 继续验证。
4. 来源 source/role/quote 必须对应真实冻结原文；原文字面相符不自动证明回答与该问题的语义蕴含。错误来源或错绑的语义拒绝必须继续保留，不能虚构已由 JSON Schema 解决。
5. 原始 wire 回执、错误、转换结果与 SHA 可审计且不可相互覆盖。根结构非法或身份集合不完整仍按原合同拒绝，不借新格式扩大 Repair 次数或把失败“洗白”。

## 4. New-Only 执行与恢复边界

- **不做历史兼容：**旧 Attempt 不迁移、不回放验收、不恢复执行，不为旧动态键格式继续建设兼容路径或测试矩阵；只保留原始数据、日志和证据，不覆盖或删除。
- **新 Attempt 只使用 P0：**新 B wire 绑定唯一 schema / decoder 身份，提交前冻结请求和配置指纹；程序中断后只校验和恢复**新 Attempt**的原操作状态。
- **PENDING/UNKNOWN 不重复派发：**不因超时、重启或解析失败重新发起已提交的有价请求；这属于新协议的必要安全性，不属于历史兼容。
- 仍使用现有 Planning Owner / 状态机，不建立第二条生产链或新 Gate。

## 5. 实施顺序（尚未获准执行）

| 阶段 | 工作包 | 验收要点 |
|---|---|---|
| S0 | 冻结 HEAD、dirty 工作区、原 B Schema、历史 Low/Medium 原件和当前测试基线 | 原件保护、身份明确 |
| S1 | B-only 显式 Schema 与 Decoder | 完整 8/8、ID 唯一合法、原合同 round-trip |
| S2 | 接入现有 B Reviewer、聚合和 Repair | `_wrapper` / `_row` / `semantic_targets` 及预算不降级 |
| S3 | 仅验证新 Attempt 冷恢复与 UNKNOWN 不重派 | 新请求身份和回执一致；不测试历史格式 |
| S4 | 正例与反例、现有回归 | 合同、来源和语义拒绝不弱化 |
| S5 | 另行获批后用新身份真实 MiniMax Medium / 完整 Planning | 不能以局部 B PASS 冒充全链成功 |

## 6. 必须覆盖的测试

- **结构：**正确 8/8、缺失、重复、额外/未知 ID、根附加字段、字段类型、错误 JSON、ID 与专属 Schema 不匹配。
- **来源：**不存在 source、错误 role、缺失 quote、quote 非原文、原值类型错配。
- **语义：**交换两个合法答案、真实但无关来源、跨 Need 错绑、Director/Truth/Rights 冲突或遗漏。**此类问题不能承诺仅靠静态 Schema 识别；须由已有领域与独立语义校验辨识并明确未覆盖风险。**
- **恢复：**仅检查新 Attempt 的冷恢复身份不变、非法根结构不能进入局部 Repair、UNKNOWN 不重复派发；历史 Attempt 不回放、不迁移。
- **完成判断：**同时满足表示合法、引用合法、语义正确、完整 Planning 成功；Demo 成功不等于生产准入。

## 7. 开放风险与实施决策

1. P0 对“模型回答挂错 question_id”没有天然语义保证，需明确是否有足够独立语义验证；如不能证明，标为开放风险，不宣称稳定。
2. MiniMax / OpenClaw 对 `oneOf`、`const`、Tool Call 和实际 wire 编译路径的支持要复核；不可因 Provider 兼容问题静默弱化 Schema。
3. 改造可能增加代码与 Schema 复杂度，必须用同输入和同模型档位衡量完整合同通过率，而不是只观察 8/8。
4. AGENTS.md 约定的跨模块边界变更需前置 Astra 复核；不可修改已冻结主合同，不得影响当前 U4→U5 或 U3-L→U6。

## 8. 当前实施进度（2026-10-14）

- **S0｜已完成本地冻结核对：**起始 HEAD 为 `d82bb60b`，原有 `AGENTS.md` 修改及本分支草案保护未覆盖；历史 Low/Medium 原始回执未改。
- **S1｜已编码并局部验证：**新增 B-only `planning-b-explicit-answer-id@1` 投影；明确 `question_id + answer`，依原 canonical Answer Schema 建立互斥分支；严格解码、缺失/重复/未知身份拒绝、不按数组位置补答。
- **S2｜已接入现有 Owner，但待完整集成回归：**新 Attempt 的当前 B correction 路径使用新格式；`_wrapper`、`_row`、`decode_answers`、`semantic_targets`、共享有界 Repair 继续消费 canonical 结果。旧 journal 仅保留原件、禁止生产接续；不为其追加兼容改造。
- **S3｜最小软件恢复验证已通过：**只针对新 P0 B 请求完成离线模拟：①持久化完整回执后重启直接复用（不派发）；②冻结 request SHA / session 改变时拒绝；③请求已登记 REQUESTED 或 TRANSPORT_FAILED、没有可验证回执时拒绝再次 dispatch，保持原状态待对账；④首次请求中途出现 DeliveryExecutionUncertain 后恢复仍不二次派发。P0 在现有 `planning_capture.capture()` 加了显式 fail-closed 选项，Owner 只对新 P0 B 使用；**未做旧 Attempt 兼容、未调用真实模型。** 未取得真正全新 Attempt 跨进程完整 Planning 的冷恢复 E2E，不能用模拟测试冒充真实端到端验收。
- **S4｜集成关键路径已局部 PASS，广泛回归未绿：**本轮修复 B 聚合 Repair 错用旧 wire 检查新 `answers` 根数组的 P0 接入缺陷，避免本可局部修复的错误被误判成根结构错误；预构建 B message 也已切换与提交一致的 P0 格式。现有真实 Medium B-001 输入的只读离线集成验证涵盖 8/8 解码、原领域 `_row`/来源校验、伪造 quote 对应单题修复目标、缺失身份根拒绝；未重调模型。`tests/test_planning_b_identity.py` 当前 19 PASS，选定新协议与投影测试合计 29 PASS。此前原格式投影测试结果仅作已有证据，不新增旧协议兼容验收；真实历史 B-001 输入离线还原及原领域校验通过。更广泛 `tests/test_semantic_planning.py` 在测试夹具的 `Planning来源Production Brief未绑定实际原件` 处提前失败，这是当前已知测试阻塞；不能声称全量回归通过。
- **S5｜未启动：**未调用新的真实 MiniMax，也未跑完整 Planning / Web E2E，未部署或 Release；新格式在本地代码中实现但**尚未获生产验收**。
- **开放风险：**交换两个语义答案但保留合法身份与引用，仍可能通过结构/字面校验；该风险不会因 P0 自动消失。需真实语义验证和完整链路证明；P1 上下文裁剪本次未实施。

**当前结论：**`IMPLEMENTATION_PARTIAL / S1_CODED / S2_WIRED / S3_S4_PARTIAL / S5_NOT_RUN / RELEASE_NOT_AUTHORIZED`。本文件仍只是分支实施记录，不修改 New-Only U0–U6 正式准入、Creator Task 或主线 Roadmap；Git 尚未提交或推送。
**2026-10-14 用户范围裁决：**取消历史兼容工作包及对应验收；仅保留历史数据不可破坏、不迁移、不恢复、不重派的保护边界。本分支后续只验证新 P0 Attempt 的运行与恢复。

**S3 完成记录（2026-10-14）：** 17 项 P0 定向测试加相关投影/版本测试共 26 PASS，`git diff --check` PASS。新 P0 的未决请求采取不重派、待对账的保守恢复语义；没有实现外部终态自动核对，也未完成完整 Planning 冷恢复 E2E。S4 全量集成回归及 S5 真实模型尚未完成。本轮未提交 Git。

**S4 本轮结果（2026-10-14）：**`29 PASS / 381 deselected`（定向测试选择；非全量 PASS）；修复原 P0 聚合路径的 wire 检查错位，测试身份缺失硬拒绝、局部错误精确定位、完整 Tool Schema 引用及共享 Repair 目标不扩张。广泛 `test_semantic_planning.py` 现有部分测试仍在 `Planning来源Production Brief未绑定实际原件` 夹具前置失败，不能混称本次 P0 错误。完整新 Attempt A/B/Truth 生产链软件集成及 S5 真实 MiniMax 尚未验证；语义错绑风险仍开放。未提交/部署。

### S4 旧夹具隔离结论（2026-10-14）

- `tests/test_semantic_planning.py` 的旧 `semantic_runtime` 夹具来自当前 `material_integration_env`（正式 Proposal @4/Handoff），却自己构造 `SCRIPT.md / SCENES.md / TREATMENT.md` 的旧式测试正文，且原 `context_refs` 只携带 `creative_mode_sha256`。进入新 Planning 前，`planning_authority.load_inputs()` 首先拒绝缺失的 `production_brief_sha256`；离线临时补足真实 Handoff hash 后，进一步拒绝 `Planning来源确认方案与三原件不符`。说明它是**历史测试输入与当前冻结确认合同不一致**，而不是 P0 Wire/Decoder 的失败。试探性测试修改已撤回，未修改或放松生产校验。
- **隔离边界：**保留该旧夹具和历史失败证据，不把其历史用例计入本次新 P0 的 PASS；不对整份测试文件添加 blanket skip/xfail，也不伪造合法 Handoff。当前执行选定的 P0 与纯投影回归：`29 PASS / 381 deselected`。此处的 deselected 表示范围外未执行，**不代表其余测试通过**。
- **仍须闭合：**用真实当前 Proposal @4 合法冻结输入驱动新 P0 的 A/B/Truth 离线 Owner 集成，检查新 B 请求、共享 Repair、Checkpoint 与新 Attempt 的恢复后，再判定 S4 能否完成。此项不是历史兼容任务，S4 保持 `PARTIAL`；S5 真实模型仍未执行。

### S4 当前合法 Proposal @4 的离线 A → B → Truth 主链验证（2026-10-14）

- 使用 `tests/test_material_integration.py::test_u2a_material_v13_current_supply_and_rights` 的**合法当前 Proposal @4、Production Brief、Handoff、Creator/Director/Truth 冻结输入**，沿现有 Web Planning Owner 与原始 A/B/Truth 软件路径运行；仅在 `tests/test_creation_preparation.py::_current_vnext_planning_executor` 更新**模拟外部 B 模型的响应格式**，使其与新 `answers[{question_id,answer}]` Tool Schema 匹配。没有触碰真实模型、Provider 或原始 Attempt。
- 首次执行如预期暴露旧模拟回执使用动态根键的 `P0 B root must contain only answers`；修复的是**当前测试模拟器**，并未放宽生产解析。
- **1 PASS（约 6 秒）**，实际执行了新 P0 B 的全部批次，`semantic-planning-vnext` Checkpoint 中 `b_identity_policy` 正确，所有 B 的 Schema Binding 均带 P0 policy，原始捕获回执根结构均为 `answers`；既有完整链路最终 Truth Ledger 为 `PASSED`，后续本地 Material 软件测例通过。
- P0 专项与所选当前投影回归另有 **27 PASS / 383 deselected**，`git diff --check` 通过。两次运行的是同一个离线场景，不可作为多样本稳定性证明。
- **S4 结论：**本分支要求的合法当前输入离线 A → B → Truth 关键链路已闭合；但大范围历史测试仍有与现行 Proposal @4 不一致的夹具，本次不做旧兼容。**S5 真实 MiniMax Medium 尚未执行，语义错绑风险仍开放，不具备正式生产/Release 准入。**

### S5 真实 MiniMax Medium 回执归因、修复与独立重跑（2026-10-14）

1. **R01（原身份，仅只读取证）：**原 B-000 Provider HTTP `RESPONSE_COMPLETE`，SSE 与 Tool arguments 完整（3,707 字节、`answers` 8/8：`question-0000..0007`），Gateway 轨迹显示 `toolUse` 和 `session.ended: success`；Owner 本地却停在 `TRANSPORT_FAILED`，Creation call 最终为 `CAPTURE_PENDING`、没有 `terminal_reply`。随后只读 `planning_transcript.read_original()` 以完全一致的 session/run/schema 身份返回 `FOUND`，证明原终态回执可读。R01 实验已停止，旧身份不再调用或修改。
2. **确定性修复：**`planning_capture.capture()` 的新 P0 fail-closed 保护保留禁止重复 dispatch，但新增原始终态 `reconcile` 路径；`semantic_boundary_run.py` 仅在同一已冻结 session 有**唯一**原 Owner call、`status=ok`、`reply_contract=planning-result-v3`、`runtime_release=released`、`terminal_receipt` 存在时，使用现有 `retry_failed=False` Owner 读取原 run 的完整回执并原位入账。未获终态证据时保持原 `REQUESTED`/`TRANSPORT_FAILED`，不重派。新增已完成回执复用、无终态拒绝的定向测试。
3. **R02（独立新 Attempt，真实 MiniMax-M3.1-Flash-Preview / Medium / 8192）：**原 R01 数据不复用、不重派；总共 14 次真实 HTTP，**14/14 `RESPONSE_COMPLETE`，A-selection + A-details 均成功，B-000..B-008 全部 `MODEL_COMPLETED`**。跨批次单次共享 Repair 也有真实 `MODEL_COMPLETED` 原回执，但原投影验收报 `Complete Planning wire schema rejected`，**最终 `result=FAIL`、`boundary_reached=false`、`pending_original_run=false`、未运行 Truth/Material/Build**。拒绝原因是 7 个修复 target 中部分 `support` 项缺失必填 `quote`、或 `source/role/quote` 联合 Schema 不合法；保留拒绝，不洗白、不增加第二次 Repair 预算。
4. **R02 后最小修改与离线回归：**仅对 `repair_message` 的 `candidate_answer` 增强具体提示，明确每个 `support` 必填 `source`、`role`、`quote`；非文本源必须显式提交 JSON `null`，文本引用必须是真实连续原文；role/source 必须满足同一 Schema 分支。原 schema、validator、共享 Repair 调用次数均不放宽。定向与合法 Proposal @4 集成测试 **21 PASS / 217 deselected**，`git diff --check` PASS。该提示调整尚未经过新的真实 Medium 验证。
5. **S5 状态保持 `PARTIAL/FAIL`，不是通过：**R02 已证明新 B P0 的 9 个批次具有实际可交接性，但最终 Planning 失败于 Repair 结果合同；模型是否能够按增强提示完成一次合法 Repair 与 Truth 需要新的独立实验授权。本次不额外启动第三个付费完整实验、不提交、不部署；此前的历史 Attempt 兼容不进入此范围。

实验独立存证：`~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5-r01/` 和 `...-s5-r02/`。

### S5-A / S5-B｜R02 Shared Repair 冻结现场审计与离线合同验收（2026-10-14）

**边界：**仅审计 S5-R02 已冻结的 7 个 `B-cross-batch` Repair targets、回执、原 Schema 和当前增强提示；无新真实 MiniMax、无历史 Attempt 回放/迁移、无 Repair 次数或 Schema 放宽。原件不更改。

- 冻结证据位置：`~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5-r02/live/eval-runtime/.../materials/recoveries/semantic-planning-vnext.json`。Journal SHA-256：`1a193231ad50dd3e763b42d6f67b38260c6cf48716df6e7433179ae3e9b1c4e4`；Repair 原回执 SHA-256：`0b15c84228c6dc227e25bb990da9f3c9c6fa9ee303a5fa84ee6ef82352162403`。不复制正文或凭证到仓库。
- 原版 `correction.patch_schema(targets, slots=True)` + `wire.project(..., 'repair')` 对原回执重验，**5 个 JSON Schema 错误涉及 3 个 target**。字段路径：`target-0000.support[1]`（缺少必填 `quote`，source-0089 为非文本 context，要求 JSON null）、`target-0001.support[1]`（source-0003 只允许 role=context，实际写了 output_authority，虽然 quote 为合法字符串）、`target-0006.support[1]`（缺少必填 `quote`，source-0005 为非文本 context，要求 JSON null）。其中 oneOf + required 错误重复指向相同字段，**不是 5 个独立目标**。
- `target-0002`（question-0047）、`target-0003`（question-0048）、`target-0004`（question-0056）、`target-0005`（question-0067）通过**结构 Schema**。这不代表来源语义蕴含已通过。7 个目标总对应问题：0020、0046、0047、0048、0056、0067、0070。
- **确定性程序结论：**原冻结 Schema 将非文本 quote 定义为必须显式 `null`，文本分支要求非空原文，source/role 的 oneOf 分支互斥；原 Decoder 的严格拒绝正确，不存在应放宽或自动补 null 的程序缺陷。当前 `repair_message` 增强提示已有三条规则：每项 support 同时填写三个字段、source 类型与 JSON null 对齐、role/source 满足同一目标的 Schema 分支。已核验这些规则确实写入约 54KB 的实际结构化请求正文，Wire guidance 使用原始 string/null 而非包装对象。**本轮没有额外修改生产代码。**
- 新增可移植离线回归 `test_p0_shared_repair_source_role_quote_contract_and_prompt`：构造 R02 同构的 source/role/quote 分支，对比合法 null、漏 quote、错 role、文本来源 null；核查现有单次 Repair 提示及严格投影，不依赖私有原件。专项与合法 Proposal @4 软件链路合计 **22 PASS / 217 deselected**，`git diff --check` PASS。再次针对冻结 R02 回执重现原 5 处 wire 错误且 SHA 未漂移。

**S5-C 一次真实 Repair 定向验证准入结论：`READY_FOR_SEPARATE_AUTHORIZATION`，不是 `S5_PASS`。** 当前新提示词与冻结 Schema 一致，合法合同、JSON null 和单一 Repair 预算均可离线验收；但是提示词增强是否能让 MiniMax Medium 一次生成有效的 7 target Repair 尚无真实证据。若用户明确授权 S5-C，应在**全新隔离请求身份**下复用 R02 冻结的 7 target 上下文和 Schema（仅读素材，不接续旧 Attempt，不补写 R02 现场），固定 Medium/8192、单次模型调用、零重试，回执先按原 Schema 完整验证，再作来源、引用、语义判定。失败保留原件并停止，不得静默补值或再次消耗 Repair 预算。S5-C PASS 只能证明单个冻结 Repair 样本合同有效；完整 A → B → Truth 仍需另行独立 E2E 验收。

### S5-C 本地脚本规范化（2026-10-14）

- 将原 `/tmp/easel_s5c_once.py` 的隔离验证入口整理为 `tests/planning_material_matrix/s5c_single_repair.py`；通过文件相对路径推导项目根目录，按 `.venv/bin/python` 启动，消除因 `/tmp` 入口导致的 `tests` 包搜索路径问题。**本次只运行 `--check`，没有调用真实 MiniMax。**
- 默认不执行：必须显式指定 `--check` 或独立授权的 `--live --authorize-one-request --run-id r<全新唯一标识>`；重复 run-id 的证据目录会拒绝，不能覆盖旧记录。真实流程硬限制单次 HTTP、无重试，R02 的数据仅作冻结输入，不向旧 Attempt 回写；不进入 Supply/Hypit Build/Release。
- 离线 `--check` 已 PASS：冻结 7 个目标、原请求 Tool Schema 完全相符，Schema SHA-256 `2a086e92be39060644cb21af5add56ab11d4ec0ac8a8344bb2fd4e7b5ae97781`，R02 Journal SHA-256 `1a193231ad50dd3e763b42d6f67b38260c6cf48716df6e7433179ae3e9b1c4e4`；本地 `py_compile` 与 `git diff --check` PASS。真实运行路径未执行、未验证，既往执行安全检查拒绝亦不因此视为解除。

### S5-C R04 单次真实尝试（2026-10-14 夜间）

- 按用户授权，将 `tests/planning_material_matrix/s5c_single_repair.py` 中 OpenClaw `thinking` 由 `medium` 改为 `adaptive`，MiniMax Provider 的 `reasoning_effort=medium` / `max_completion_tokens=8192` 不变。项目 `.venv` 的 `py_compile`、`--check` 和 `git diff --check` 通过：原 7 target、冻结 schema SHA 与 R02 journal SHA 一致。
- 新隔离身份 `r04adaptive20261014`，独立路径 `~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5c-once-r04adaptive20261014/`。**唯一一笔 HTTP 已在代理账本登记，但未取得任何 Provider 流回执**：代理返回 HTTP `502`，请求记录为 `UNKNOWN / INCOMPLETE`（SSE events=0、response bytes=0、`ARGUMENT_STREAM_MISSING`/`HTTP_BOUNDARY_INCOMPLETE`/`TOOL_FINISH_MISSING`），Gateway 报 `STRUCTURED_EXECUTION_FAILED`。OpenClaw 本地日志显示后续 `empty-error-retry` 尝试，但本次硬限制阻止产生第二笔 HTTP。实验结果 `GATEWAY_NOT_OK`，非模型 Repair Schema PASS/FAIL。
- **Fail closed**：不重试、不接续、不修改旧记录；本轮 S5-C 真实 Repair 尚无可验证的模型 Tool 回执，不能宣称成功或认定模型回答不合法。下一步先只读调查隔离代理 HTTP 502 的入口失败原因和 OpenClaw 内部重试控制，修正确定性配置问题后再单独授权全新身份验证。

### S5-C R05 单次真实 Medium Repair（2026-10-14）

- 已对隔离脚本 `tests/planning_material_matrix/s5c_single_repair.py` 修复 `proxy.deadline=time.monotonic()+900`，原 OpenClaw `thinking=adaptive`、Provider `reasoning_effort=medium`、8192 输出上限不变。离线 `--check` 与编译检查通过；独立新身份 `r05deadline20261014`，一次真实 MiniMax 请求，不重派 R04 或 R02。
- **HTTP 1/1 `RESPONSE_COMPLETE`、参数流 `COMPLETE`**，Gateway `ok`，只读原 Tool receipt `FOUND` / `toolUse` / `tool_calls`，Schema 身份 `2a086e92be39060644cb21af5add56ab11d4ec0ac8a8344bb2fd4e7b5ae97781`，响应 3512 字节、7 个 target 键完整。
- **验收结果 WIRE_FAIL**：唯一错误 `target-0000.support[1]` 的 `oneOf`。模型提交 `source=source-0089, role=context, quote="8.0"`；此冻结 source 属于非文本分支，Schema 明确要求 `quote: null`。其余项通过当前 Wire Schema 检查；这不等于领域来源蕴含或 Truth PASS。无补值、无第二次 Repair，原始 Tool 回执 SHA-256 `0fa350d581522b99c3dd0d702c12c6dc09600e8733a29bec9ec7a900355e39ad`。
- 原始实验目录：`~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5c-once-r05deadline20261014/`。**S5-C 的单次真实结果是合同 FAIL，不具备进入 S5-D 完整 Planning 的准入。** OpenClaw 内部空结果重试机制尚未另行确认关闭；本次 HTTP 硬上限得到遵守。

### S5-C 后续：非文本 quote 易错问题的模型表示层改进（2026-10-14）

- R02 / R05 同一个结构风险：`support.source` 对应**非文本**冻结 source 时，`quote` 必须为 JSON null，R05 在 `target-0000/source-0089` 上仍误填字符串 `"8.0"`。领域 Schema 与严格 Decoder 拒绝正确；禁止自动将字符串改为 null，也禁止放宽 `oneOf`。
- 采用 **无损辅助提示，不修改输出合同**：新 `repair_quote_null_guidance(schema)` 只遍历提交用的冻结 Repair *wire* Schema，按 `target-XXXX` 提取 quote 限制为 null 的 source ID；`repair_message()` 将 `quote_null_source_ids_by_target` 提供给模型，并强调这些 source 的 quote 必须是 JSON null（即使源内容看起来像文本/版本）。该字段仅为模型可读提示，不属于模型输出；唯一验收仍是原冻结 Tool Schema、原领域来源与语义校验。
- 真实 R02 冻结的七个 Repair 目标，离线提取均各有 16 个非文本 source，**R05 失败的 source-0089 已明确进入 target-0000 清单**；没有扩张可用来源、Repair 目标或 Repair 预算。
- 新增专项正/反例测试，验证从已展开的 wire `oneOf` 分支提取 null-source 清单、合法 `quote: null` 仍通过、非法 `"8.0"` 仍拒绝。定向 + 当前合法 Proposal @4 软件集成 **23 PASS / 217 deselected**，编译及 `git diff --check` PASS。
- **尚未真实验证**新辅助清单能否提高 MiniMax Medium 成功率，不将离线通过标为 S5-C PASS。后续如进行单次真实验证必须使用新隔离身份、额外授权，保留原响应，HTTP 上限 1、无重复消耗；完整 Planning/Truth 仍不在本次范围。

### S5-C R06：非文本 source 清单提示真实 Medium 单次验证（2026-10-14）

- 全新隔离身份 `r06nullguide20261014`，证据目录 `~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5c-once-r06nullguide20261014/`。在相同 R02 冻结七个 Repair 目标及原 Tool Schema 上，新增 `quote_null_source_ids_by_target`，每个 target 的 16 个非文本 source 均由冻结 wire Schema 推导；R05 曾出错的 `source-0089` 包含其中。未更改领域 Schema、Decoder、Repair 次数、来源或原件。
- 独立真实 MiniMax Medium / 8192 调用 **恰好一次 HTTP `RESPONSE_COMPLETE`**，参数流 `COMPLETE`，Gateway `ok`，原始回执 `FOUND`（3761 字节）、工具身份/Schema SHA 一致，七个目标完整。结果 **`WIRE_FAIL`**，原始回执 SHA-256 `312a537c93d755c1b83befbddd1d1222eecb69b70204afac0c0fe7d2f63c9ae2`。
- 严格 Schema 错误 3 条、涉及 2 个目标：`target-0000.support[1]` 的 `source-0089` 非文本 context，模型把 `quote` 填为空字符串 `""`（必须 JSON `null`；触发 `minLength` 与 `oneOf`）；`target-0001.support[1]` 的 `source-0003` 只允许 role=`context`，模型仍填 `output_authority`（触发 `oneOf`）。清单提示未解决实测失败，不可宣称稳定性改进有效。
- 本次不重派、不自动清洗字符串/角色、不补发第二笔请求。下一步若继续研究，应比较保持原领域合同下的**真正互斥 tagged union 输出表示**或减少模型填写由 source 唯一确定的冗余字段，且必须证明无损逆向映射与来源、语义校验不降级；在新设计离线验证前不建议再直接烧一次相同提示的真实调用。S5-D 完整 Planning 未准入。

### Shared Repair Evidence Projection｜New-Only 最小实施包（2026-10-14）

- **实现：**新增 `easel/integrations/planning_repair_evidence.py`，遵循内部 `SourceSelection` 的冻结注册表模式。从原 `patch_schema` 经既有 `FrameProjection` 展开后的每个 target `support.items.oneOf` 枚举合法 `(source, role, quote-kind)`，依据 `target/source/role/quote-kind` 内容散列生成稳定 `ev_...`，按 target 分开授权。文本分支模型必须明确提供非空 quote；非文本分支不允许携带 quote。解码时仅展开**模型确实选择过**的合法 ref，确定性还原 source、role 及非文本 null；原 canonical Schema 与业务校验完全保留，未知 ref、跨 target、非法角色、额外字段或引文仍拒绝。没有自动选择证据、自动造引用或洗白模型的语义判断。
- **性能与约束：**每个 target 以两条互斥分支（文本与非文本）的 `evidence_ref enum` 表示合法源角色组合，不用每个 ref 一个 oneOf 分支。保留原 `ACCEPT` 必须包含 authority/output_authority 的 `contains` 规则，编译为相同角色对应的 ref 枚举；未识别的交叉条件拒绝编译而不是删除谓词。原范围单次 Repair、预算、Owner 状态机均不变。
- **接入：**仅**新** P0 Planning Journal 冻结 `repair_evidence_policy=planning-repair-evidence-ref@1`，现有 `invoke/candidate/repair_message` 和最终 Checkpoint `verify` 根据冻结 policy 选择投影并校验身份。旧原件不迁移、不恢复生产；不创建第二条主链。Repair 提示与 Tool Schema 同步切换；模型请求带 `evidence_choices_by_target` 显示稳定 ref 与原 source/role/quote-kind 的冻结映射，避免旧提示要求同时填写 source/role/quote 的冲突。
- **离线验收：**新增 `tests/test_planning_repair_evidence.py`，正反例覆盖稳定 ID、无损编码/解码、非文本 quote 不由模型填写、文本 quote 必须明示、未知/跨 target ref、角色伪造、文本空引用及 `contains` 权威来源义务保留。R02 保存的真实 7 targets 编译出 **1323 个合法 target-scoped 选择**，模型请求 198822 字节、处于原请求容量约束内；对一份**仅在本地临时副本中修正结构字段**的合规样本完成严格无损往返（约 0.01 秒），R05/R06 未修改原始回执均被原 canonical 严格拒绝。精确选定回归 **34 PASS / 6.25s**，含合法 Proposal @4 A→B→Truth/本地 Material 软件集成；`py_compile` 与 `git diff --check` PASS。
- **限制与准入：**这里只证明离线表示/反向合同和已选软件路径；真实 MiniMax 对新 Evidence Projection 的生成能力**未测试**，该改造不能证明语义 entailment 的正确性，也不能把 R05/R06 失败回执转为通过。不改变正式 U0–U6、Material/Truth 领域合同。根据 AGENTS.md，跨模块新表示在正式冻结/真实 E2E 前需独立正确性复核。**RESULT=PARTIAL（实现与定向离线验证完成，正式准入未完成）；DRIFT=NO_DRIFT；NEXT_SINGLE_ACTION=独立复核新 Repair Evidence Projection 的冻结映射、谓词等价性及 Checkpoint 恢复身份，再决定是否另行授权单次真实 Medium 测试。** 未提交或部署。

### Shared Repair Evidence Projection｜Checkpoint 真实 Owner 离线 E2E 与篡改验收（2026-10-14）

- 新增 `tests/test_material_integration.py::test_newonly_repair_evidence_checkpoint_cold_verify_and_tamper`，复用**合法当前 Proposal @4 / Production Brief / Handoff** 的本地 Owner：模拟 B 原模型回执的一条引用字面错误，真实触发共享 `B-cross-batch` Repair；模拟的 Repair 使用 `RepairEvidenceProjection.encode()` 生成冻结 `evidence_ref` Wire 回执，沿原 Owner `invoke/candidate/decode_patch_slots/apply_patches` 保存 Recovery Journal 及 Planning Checkpoint，后续完成原本地软件链。
- 断言新的 `repair_evidence_policy` 同时存在于 Recovery Journal、`schema_bindings['repair']`、`SEMANTIC_CHECKPOINT.json`；原 `wire_originals['repair']` 必须是模型选择的 `evidence_ref` 而不是静默改写后的 canonical source/role/quote。通过真实 `semantic_boundary_run.verify()` 对保存原件冷校验；分别篡改 Checkpoint policy、Repair Wire Schema SHA、原始 Evidence Ref 与原捕获 `reply_sha256`，四种情况**均拒绝**，然后复原原字节并再次 cold verify 成功。
- 配套调整仅限测试模拟器 `tests/test_creation_preparation.py::_current_vnext_planning_executor` 可选 `repair_probe=True`。默认软件主链保持原行为，不调用 MiniMax/Provider。
- 最终精确回归：`tests/test_planning_repair_evidence.py` + `tests/test_planning_b_identity.py` + 上述 Repair E2E + 原 `test_u2a_material_v13_current_supply_and_rights` 共 **35 PASS / 11.76s**；Python 编译与 `git diff --check` PASS。
- **结论：本次请求的 Checkpoint 保存、冷加载、版本标记/Schema Identity、非法 Evidence Ref、回执 SHA 篡改的关键软件 E2E 已 PASS。** 仍不是跨进程真实模型恢复或线上稳定性证明；未调用真实 MiniMax、未修改原始 R02/R05/R06 回执、未提交/部署。因当前可用工具没有独立 Astra Reviewer 执行入口，**不能声称已得到 Astra 独立签核**。冻结前签核维持 `PENDING_EXTERNAL_REVIEW`，不得因此自动启动真实 S5-D/Release。

### S5-D 单次真实 MiniMax Medium Evidence Projection（2026-10-14）

- 用户明确授权后以全新隔离身份 `r07evidence20261014` 执行，原始证据 `~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5d-once-r07evidence20261014/`。脚本 `tests/planning_material_matrix/s5d_evidence_single_repair.py` 独立于 S5-C，沿 R02 冻结七目标、原输入与原模型，仅将 Repair Tool Schema 替换为 `planning-repair-evidence-ref@1` 并提供冻结 evidence 选择表。无旧 Attempt 重派，无下游制作。
- **一次真实 HTTP**，状态 `RESPONSE_COMPLETE`，Gateway `ok`、Tool receipt `FOUND`、`tool_calls`、schema SHA `edef995f913405f3f04911006811dfe4dc5c8a7ace120b72251cba32a098825a`；七个 target 全部返回、原回执 3279 字节、回执 SHA-256 `332fca76b4c959d27fd2b4586c5522392c0d337ed7dfc1a0387bb2ce9a5c5887`。
- **结果：`WIRE_FAIL`**。唯一失败 `target-0005.support[1]`：模型提交 `evidence_ref=ev_28bbde01a20e50d5da48ba82` 及 quote 字符串，该 ref **不属于 target-0005 的冻结合法选择集**，而是 `target-0001` 的合法来源 `source-0052 / authority / string`。确定性的跨 target ID 混用，当前严格 oneOf 正确拒绝；**不得自动迁移该证据到 target-0005、不得从 quote 猜 source、不得放宽 target-scoped 验证**。
- 离线 Evidence Projection 的 `quote:null` 重复错误已从此次实际回执中消失，但在这**一例**中暴露了跨 target ref 选择错误；尚不能断言稳定性改善，更不能作为完整 Planning/Truth PASS。真实 Repair 在 Schema 阶段停止，零补发、零重复消费。下一动作只针对减少跨目标引用混淆的模型可选表示/请求负荷进行独立设计与离线验证，不继续烧同类请求。`RESULT=PARTIAL`；S5-D 模型准入 FAIL，完整稳定性验证 HOLD。

### S5-D R07 之后：跨目标引用错误的只读离线表示分析（2026-10-14）

- 从 R02 冻结 7 target 直接重建现有 `RepairEvidenceProjection`，结果每个 target 均有 **189** 个合法 `(source,role,quote-kind)` 组合，其中 **168** 文本、**21** 非文本，涉及 **118** source；7 target 全部组合集合**完全相同**，合计 1323 个 target-scoped 长 ref，但全局仅 189 种不同 tuple。
- R07 唯一错误：`target-0005.support[1]` 所选 `ev_28bbde01a20e50d5da48ba82` 是 `target-0001` 的合法标识，映射 `(source-0052,authority,string)`；**该三元组本身也是 target-0005 的合法组合**，仅 ID 由于包含 target 名而不同。当前 Schema 正确 fail-closed；不能直接将旧回执的错误 ID “修好”或冒充成功。
- 只读离线对比：现有 Schema JSON 63538 bytes；按冻结 tuple 排序、target 上下文隔离的简洁 `e000..e188` 同义映射，保留每一原选项、文本/非文本分支及 `ACCEPT contains` 原角色映射，Schema JSON **21678 bytes（-65.9%）**。此计算只模拟映射和 Schema 字节数，未替换生产编译器或运行真实模型；不证明 Token/模型成功率相同程度改善。
- 推荐候选：**target 槽位限定的稳定短 Evidence Ref**（例如 `e100`），同一 tuple 在同一冻结目录中使用同一短代号；还原时必须以 `target` + freeze/map fingerprint 作为命名空间，拒绝未登记 ID，并对所有原 source/role/quote-kind 及业务谓词做完整严验。虽然局部 ID 在不同目标复用，但模型的回答仍位于对应 target 的确定槽位里；不代表允许跨目标移动答案。不能裁剪任何合法候选、自动取舍 quote 或移除独立来源/语义校验。
- `RESULT=ANALYSIS_COMPLETE`，没有新增模型请求、没有修改生产代码或原实验；`NEXT_SINGLE_ACTION`：先在独立纯离线试验中实现短 ID + 冻结注册表身份/篡改测试，并和现有长 ID 做差分往返，验证 1323/1323 组合无损、谓词等价、Checkpoint 冷验证后再考虑任何新真实 Medium 请求。

### Frozen Local Evidence Ref｜离线差分与 Checkpoint 恢复验收（2026-10-15）

- 在既有 `RepairEvidenceProjection` 新建 New-Only policy `planning-repair-evidence-local-ref@2`：从冻结 Repair Schema 枚举所有 `(source,role,quote-kind)`，排序分配 `e000...` 短代码；一个 tuple 在各 target 使用同一代码，但每个 target 仍仅允许本 target 原有的完整枚举，解码从当前 target 的独立映射解析，不能跨 target 提权。`frozen_mapping_sha256` 加入新投影身份，Schema SHA 与 policy 随之变化；原长哈希 `planning-repair-evidence-ref@1` 保留显式只读重放解码路径，已有冻结版本不会静默迁移。
- 与真实 R02 冻结七 target 差分：v1 和 v2 各 **1323 / 1323** 个合法映射，所有 target tuple 集合完全一致（每个 189）、没有剔除选项；经本地修正结构错误的合法回执在两版本均严格无损往返；非法 ref、错误 source-role、跨不同候选 target、假 quote、`ACCEPT` 缺权威来源保持拒绝。新 schema 使用短 ID，减少重复长哈希，不改原 canonical 或语义校验。
- 保持 Owner 单次 Repair、Checkpoint 原回复原件、HTTP/Provider 边界不变；`semantic_boundary_run` 新建记录保存 v2 版本，并在 `run` 与 `verify` 中按冻结 policy 重建同版本投影。真实当前合法 Proposal @4 的离线 Owner Repair → Checkpoint 保存 → 冷 `verify()` E2E PASS；Checkpoint policy、Wire Schema SHA、**映射 SHA**、原始 Evidence Ref、原捕获 reply SHA 分别篡改均正确拒绝，恢复原件再次 PASS。
- 精确离线回归：`tests/test_planning_repair_evidence.py`、`tests/test_planning_b_identity.py`、`test_newonly_repair_evidence_checkpoint_cold_verify_and_tamper`、`test_u2a_material_v13_current_supply_and_rights` **37 PASS / 12.70s**；`py_compile` / `git diff --check` PASS。无真实 MiniMax、无生产迁移/历史 Attempt 修改、无 commit/push。
- `RESULT=OFFLINE_PASS`；`DRIFT=NO_DRIFT`；`NEXT_SINGLE_ACTION=针对新 v2 短 ID 策略准备一次隔离的真实 Medium Repair（需单独执行授权），保持原 R02 七 target、单 HTTP、零自动重派及完整原件。` 离线验收不代表真实模型成功率提高。

### S5-E R08｜真实 MiniMax Medium 冻结短引用 Repair 验证（2026-10-15）

- 用户单次授权，新隔离身份 `r08local20261015`；测试脚本 `tests/planning_material_matrix/s5e_local_single_repair.py`，原件位置 `~/.local/share/easel/creator-task-evidence/2026-10-14-real-minimax-p0-medium-s5e-once-r08local20261015/`（目录名沿 10 月 14 日实验系列）。来源仍为 R02 七个冻结 target、原请求与原模型，输出使用 `planning-repair-evidence-local-ref@2`。离线预检确认 source journal SHA `1a193231ad50dd3e763b42d6f67b38260c6cf48716df6e7433179ae3e9b1c4e4`、新 Tool Schema SHA `f83114bfd08eef6bb75aa9b7cce0b945cebce8af01f16fbbf24f314d9d4d5a80`。
- **恰好 1 笔真实 HTTP**，账本 `RESPONSE_COMPLETE`，Gateway `ok`、Tool receipt `FOUND` / `tool_calls`，全部 7 target 返回，严格 Evidence Wire **0 errors**，成功 `decode_valid` 成 canonical；原回执 4091 bytes、SHA256 `08d9d99833da3ebf1e570c6df82fcc0c4c2fbfb2abc234d8c91e65d23c0d0303`。结果 `WIRE_PASS_DOMAIN_NOT_YET_VERIFIED`，没有重试或重新派发历史任务。
- 后续只读将解码后七组 support 对照 R02 冻结五个原 B batch 的 question/evidence/source catalog，核对来源存在、角色允许、证据 ID 在原 question 合法集合、文本 quote 是原 source 连续子串及非文本 quote 为 null，观察 **0 eligibility errors**。这是来源/引用资格检查，并非语义蕴含真值裁定；尚未运行完整 Owner B repair→Truth、Plan 保存/载入与独立语义验收，不得标记完整 Planning 成功或正式稳定性通过。
- `RESULT=S5-E_WIRE_PASS / SOURCE_ELIGIBILITY_PASS / SEMANTIC_NOT_YET_VERIFIED`。继续保持 R02/R05/R06/R07/R08 原件不变、单次调用预算不扩、New-Only U0–U6 门禁不越级、无 Material Supply/Hypit Build/Release。下一单一动作：使用**当前 R08 回执**离线进行原候选补丁应用、B 独立语义判定/Truth 准入检查；不自动发新的模型请求。

### S5-E R08 已保存回执：离线补丁、B 语义和 Truth 准入（2026-10-15）

- **无新 HTTP/模型调用。** 从 R08 `response.json` 经 `RepairEvidenceProjection(local-ref@2).decode_valid` 严格解码、原 `decode_patch_slots`、`apply_patches`，将 7 项补丁应用于 R02 原 `B-cross-batch` frozen original。仅内存副本改变，目标严格为 `question-0020/0046/0047/0048/0056/0067/0070`；未修改 R02 或 R08 原件。
- 从 R02 冻结九份 B model response 与九份 B request 原文重建 72 个问题及 batch；在冻存的 `supported` source policy 下，用原 `candidate_review._row`/`decode_answers` 对重组结果逐批验收：**9/9 batch、72/72 question、7/7 repaired row PASS**。注意仅解码和引用合法性 PASS，不是全部决策 ACCEPT。
- 最终决策数量：**63 ACCEPT、8 CHALLENGE、1 UNRESOLVED**。依原冻结 question directory 汇总未通过完整义务：`question-0002/0004/0007/0034/0036` CHALLENGE，`question-0041`（complete_obligation，[6,0]）UNRESOLVED；未决分类 `question-0065/0066/0068` CHALLENGE。上述均不在 R08 的 7 个修复槽位内，不能由 R08 自动改判。
- 对冻结 questions 的必要原始 Need/未决报告建立最小无推断内存上下文，直接执行原 `planning_candidate_review.semantic_targets(...)`：**拒绝 `ValueError: Independent semantics remain unresolved`**（最早明确未决 complete obligation `question-0041`；后续未决报告分类也存在 CHALLENGE）。因整套 Planning 共享 Repair 已由 B-cross-batch 消耗，**不得继续另发 semantic Repair**；Truth 准入为 `BLOCKED_BEFORE_TRUTH`，没有进入 Truth，也没有 Plan 保存/load 证据。来源 eligibility PASS 不能充当语义 PASS。
- `RESULT=R08_B_PATCH_APPLIED / ALL_B_ROWS_VALID / INDEPENDENT_SEMANTIC_REJECT / TRUTH_NOT_ADMITTED`；`DRIFT=NO_DRIFT`。`NEXT_SINGLE_ACTION`：只读定位原 R02 尚存 9 条 CHALLENGE/UNRESOLVED 的冻结原因与最早实际阻塞，并评估需否在**下一次全新 Planning 实验**中重新分配唯一 Repair 的策略；不得复用或修补旧 R02 Attempt、不得自动调用模型或下游发布。

---

> **后续详细实施蓝图（待批准）：**[Planning Creative Authority & Decision Provenance｜New-Only 实施方案](planning-creative-authority-implementation-plan-2026-10-15.md)。该文件具体列明 D0–D4 的实际代码落点、版本边界、测试与停止条件，不取代本分支 R02–R08 原始证据，也不构成执行授权。

## Planning Creative Authority & Decision Provenance｜架构方案评审（2026-10-15）

> **状态：PROPOSED / ARCHITECTURE_REVIEWED / NOT_APPROVED_AS_CURRENT_CONTRACT / NO_RUNTIME_CHANGE。** 此节是根据 R02 九例及当前产品/源码完成的候选设计评审，不替代 `docs/00_PROJECT.md`、CURRENT Architecture、Material V1.3/ADR-004、New-Only U0–U6，也不成为新的并行 Task/Gate。独立 Astra 签核未执行；以下为本轮项目证据与架构推理结论。

### 目标、判断与选型

产品目标：一个 Creator/Profile + 一个冻结 Director/Creative Mode + 多种 Content，Creator 确认 Proposal 后由 Easel 尽量自主交付可审阅首版。**真实性、授权、费用必须强校验；Director 的合法 HOW 决策不能被误当成无来源的 Creator 事实，也不能无审查变成昂贵的素材硬条件。**

- A｜原 B 不变，仅继续补 Prompt：**REJECT**。缺少授权与消费责任的类型化绑定，无法消除语义矛盾。
- B｜所有导演新细节均可 ACCEPT：**REJECT**。会产生事实造假、Required 膨胀、Rights/费用越权及下游硬规则丢失。
- C｜新增独立 Director Agent/状态机或重建 Material/Truth：**REJECT FOR V1**。违背单 Creator Task/唯一 Owner、成本高且制造双主链。
- **D｜有界 Director Delegation Envelope + Planning-local Decision Proof + B 分类型审核 + 已有 Material/Authoring 消费验证：RECOMMENDED。** 复用 `planning_authority.catalog`、现有 A/B/Checkpoint、`SourceSelection` 与 Evidence Projection，不变更 Material V1.3 Domain。

### 有界导演委托：拟议政策（非既有隐式无限授权）

Creator 对当前 `Proposal @4`、Creative Mode 的确认，建议明确视为授权 Director 在本 Creation 内作出**不改变 WHAT、只具体化 HOW** 的审美与镜头实现选择。该委托须由程序绑定 `proposal_sha256`、`creative_mode_sha256`、Creation/Attempt、Script/Scenes/Truth/用途与费用许可边界；模型不能声明自己获得了新的权限。

**允许建议/作出：**镜头景别与构图、光线/色调、拍摄手法、剪辑节奏、局部视觉连接、具体素材呈现方案，前提是服务已确认场景与冻结导演语言；可以有 Director 承诺的硬性选择，但须通过独立 B 的必要性/可消费性检查。**不允许：**修改已确认文案/场景义务/声音模式/事实/真实人物身份或经历；认定素材、Rights、授权、预算、可用性已取得；创造物理同一身份或同一 licensed-source 要求来冒充 Creator 决定；擅自决定 Provider/Asset/Hypit Timeline/正式 Build。

### 决策类型与三维度

现有 `Condition(text,strength,responsibility,meaning)` 的 `required|preference`、`material|postproduction|narrative` 原样保留；仅在 **Planning 内部**增一份可版本化、非正式 MaterialNeed 字段的 Decision Proof，由程序按实际 Need/Condition 路径及内容 SHA 赋 ID：

- `authority_kind`: `confirmed_obligation`（已确认硬义务）| `frozen_director_rule`（Mode 已有规则）| `director_local_choice`（本次创作委托内的新取舍）| `creative_preference`（可替换方案）| `program_derived`（只能由程序负责的机械事实）。该字段是 A 提议、B 审核、程序归档的结论，**不是 A 自签权限**。
- `basis`: 只引用冻结 Proposal/Scenes/Creator/Mode 的真实身份与适用 scope；`director_local_choice` 不需伪造源文件里逐字出现此内容，但须明示服务的已批准叙事目标和创作理由，绝不能自证事实。
- `strength`: 保持现有 `required|preference`。`director_local_choice` 允许经 B 接受后成为本次 Attempt 的 Required，而不是 Creator 永久硬要求；不能把 soft Mode 偏好自动升级为 Required。
- `responsibility / enforcing_consumer`: 原 `material|postproduction|narrative` + Planning 内部消费证据；只有可由 Material Observation 或正式 Authoring/Quality 实际验收的条款才能承诺 Hard。无消费证明时不能默默写进 `intent.function` 就声称硬约束已闭环。
- `decision_proof_identity`: 输入哈希 + scope + condition text/strength/role + policy revision + B 审核回执；伴随原 Owner Checkpoint 冷校验。不新增产品 CRUD/状态机。

**Hard 的准入：**已确认上游硬要求不得降级；导演新增 Hard 必须是有意义的本次创作承诺、未与冻结事实上矛盾、未越权，且责任方能够执行/核验。若只是可替换的视觉建议，应保留 preference；若 Hard 确有必要但现有消费者不能履约，应显式阻断或先实施消费合同，不可当成软分数放行。

### B 分类审核规则（保留同一 B / ACCEPT, CHALLENGE, UNRESOLVED）

1. `CONFIRMED_FIDELITY`：已确认 WHAT 是否完整、未改、无冲突；此类必须有真实冻结证据。缺实证事实/侵犯身份/改变脚本应拒绝，不以 Director 自由开脱。
2. `DELEGATED_CREATIVE_VALIDITY`：新增 HOW 是否属于授权选择空间，服务哪个 Scene 目标，是否符合冻结 Director/Creative Mode，是否必要且符合声明强度。不要求创作新细节在 Script 中逐字出现，但也不让 A 的选择自身成为合法依据。
3. `RESPONSIBILITY_AND_ENFORCEMENT`：是素材可观察属性、编辑/叙事意图，还是 Provider/Rights/费用的执行事实；需要 Hard 时下游真实消费者与验收是什么。不能让 Material 修改导演权，也不能把 continuity matching 加权评分当成硬保证。
4. `COVERAGE_AND_UNCERTAINTY`：是否遗漏确认义务；Unknown 应区分 `creator_decision_required`、`director_replan_needed`、`material_supply_pending`。真实素材/Rights 尚未检查不是自动阻断 Planning 的理由，**但不得预先写成 READY 或授权已获得**。

保留原三态；建议给 B 的内部审核结果补充 `issue_code`/`issue_owner` 与目标决策身份，程序核对。`ACCEPT`：事实未改 + 创作在授权边界内 + 强度/责任/消费契约成立；`CHALLENGE`：可明确定位违反或可在 A 内修正的规划错误；`UNRESOLVED`：存在不可由本次受委托 Director 决定的必要未知，不得假装可用。美学优劣由后续 Creator Review/Quality 检查，B 不应将纯审美争论变成必须从原文摘录的事实证明。

### R02 九例反例矩阵（方案预期，不是改写历史模型标签）

| ID | 原始结果 | 需辨认的语义 | 拟议策略 |
|---|---|---|---|
| 0002 | CHALLENGE | 水杯移动是确认动作；无遮挡/剪辑不跳过是可能的导演实现 | 动作所需可见事实按材质检查；剪辑方式移交 Authoring；合理 Director 承诺可以 Hard，但需说明必要性与可执行消费 |
| 0004 | CHALLENGE | 接触及“嗒”声确认；禁止淡出/替身属于编辑手法 | 不允许把编辑禁令伪装成源素材硬属性；若选为关键导演约束则 Authoring/Quality 核实 |
| 0007 | CHALLENGE | 跨镜复用与不同机位是许可/选择策略 | 不作为上游硬义务或 Material Hard；Production 选材与连续性评分不能自动认为授权 |
| 0034 | CHALLENGE | 确认场景“空桌面”；Mode 支持 negative space；“基本归位”可能与空冲突 | 空桌面义务优先；构图留白可为导演 preference，只有经 B 判断目标必要且可执行才可 Hard |
| 0036 | CHALLENGE | 窗光更明显为原场景；偏冷/低饱和为不同审美取舍 | 窗光可为确认义务；偏冷若 Mode 未强制，应作为本次导演取舍而非声称原文 Required |
| 0041 | UNRESOLVED | 收尾天色安静为确认；明亮不刺眼为额外曝光取舍 | 可作为导演曝光偏好；不因未逐字来自场景就必然 BLOCK，若要求源图 Hard 需证明委托与消费者 |
| 0065 | CHALLENGE | 分镜 1/6/7 视觉世界连贯，与同一物理桌面/同一 licensed source 非等价 | 允许画面连贯选择；不能将相同授权来源当强制事实；真实来源/权利留给 Material |
| 0066 | CHALLENGE | 同一手/桌面连续性是否实际委托 | 可选视觉连贯意图；没有已确认身份/参考时，不得声称物理同一人/同一来源 |
| 0068 | CHALLENGE | 0065 类连续性义务在未决报告重复出现 | 去重重复的规划疑问，区分 `director_replan_needed` 与 `material_supply_pending`，不允许删除真实 Creator 不明义务 |

### 下游真实消费风险：架构评审的阻塞条件

1. 当前 `semantic_boundary.project_proposal()` 对 non-material 条件主要编入 `intent.function`（文字），这**不等于** Native Authoring/Hypit 已核验镜头/剪辑 Hard。必须检查正式 Authoring 接口能否消费与独立验收，否则 Hard 不得标闭环。
2. 当前 `material/application/matching.py` 通过 `continuity_refs` 计算 weighted continuity score（当前权重 0.20）。**此 soft signal 不提供同一物理身份/同一镜头连续性硬担保。** Hard 连续性必须有另外的合法观察/Authoring/Quality 证明；缺能力时 fail-closed，而不是修改 Material V1.3 来掩盖。
3. `unresolved_classification` 的非 ACCEPT 在 `planning_candidate_review.semantic_targets()` 可直接 raise，且整个 Planning 共享 Repair 一次。新设计应对 B issue 先区分需要 Creator、需要 Director 局部 replan、仅有 Material pending；修复调度可重组一次预算内的候选与缺陷，不得删除来源真实性/增加隐式付费调用。无法修复时终止，不以全部 ACCEPT 为唯一“审美成功”指标。
4. Decision Proof 与 Required/Preference 的正式投影须经完整原合同、Source/Role/Truth/Material Gate 和 Checkpoint 证明，不允许侧车元数据绕过已有正式字段校验。改变上游 Proposal @4 事实需 Creator 重新确认，不能借 Repair 静默篡改。

### 最小实施验证计划（目前未实施）

- **D0：合同决策表**：冻结委托范围、Creator 禁区、Director 决策强度和实际消费者映射，确定 9 例中哪些可接受、哪些必需 A 改写、哪些只能移交 Material；先以可证伪反例达成设计一致。
- **D1：最小 Planning 内部 Proof**：借现有 `planning_authority` 与 `planning_input_view` 承载 authority 类型/真实引用；不在 MaterialNeed 增字段、不造第二状态机，原 A/B schema 的结构性改动保持版本化 New-Only。
- **D2：B 分类审核 + 单 Repair**：对确认事实与导演取舍分型审核，提取可定位的 A 修复目标；保留一次共享预算、B Identity/短 Evidence Ref；严格不为原 R02 补造过去答案。
- **D3：Consumer/Truth 验证**：material required、postproduction hard、continuity hard 三种代表性穿透 A→B→Material/Authoring/Quality，Truth 事实边界不受侵犯；编排/资源未知必须真实停在 MaterialGap 等合法 Gate。
- **D4：新隔离 Attempt 验证**：离线正反例+Checkpoint 冷恢复 PASS 后，独立授权真实 MiniMax → Planning/Truth；旧 R02/R08 原件全部保全，无自动重复模型或 Provider 调用。正式 Web U4/U5 Gate 不自动改变。

### 评审结果

- **RECOMMENDATION = D / MINIMAL_PLANNING_INTERNAL_AUTHORITY_CONTRACT**。
- **DESIGN_REVIEW = CONDITIONAL_PASS**：原则与责任边界吻合现行产品/架构，尚未取得冻结设计变更授权；需要解决非 Material Hard 和 Hard Continuity 的明确消费者证明，审阅方案不能偷换为生产准入。
- **IMPLEMENTATION = NOT_STARTED**。仅新增本节拟议评审记录，无生产代码/合同/状态/模型调用更改。正式下游 Gate 与既有 R02 原件维持不变。
