# Planning Semantic Boundary vNext：软件通过，Development 失败停止

本记录不认领正式R4、Material Smoke、Material E2E或MATERIAL_READY。软件冻结commit `aa0ab42ac86305d818613bc4a078469eb2042918`，production source SHA `ffac01cc608caf72790d2a71d5bdf813657bc7ade24be09f31c4347ea651c74d`；基线 `3be0ff946c29c8871a8f34de015c8b3944316ac7`。服务未重启，真实评测进程从固定源码导入Web模块，沿原Owner/Preparation/Planning链隔离执行。

## 软件证据

S1–S5确定性软件Gate通过；最终矩阵run-032：196 PASS/0 FAIL/0 CONTRACT_GAP/0未执行，针对31 PASS，全量934 passed/5项既有skip；技能115、compileall和本期diff通过，前端未改。Astra实际diff先MODIFY，六项最小修正并补中断回归后CONTINUE。它只同意软件冻结，不证明模型语义能力。历史十批1550文件与257现场/117fixture运行后指纹仍一致，10批FAIL/12执行/held-out0原记录不改。

A不再维护正式ID/path/hash/alias/sidecar/缓存；程序拥有绑定、投影、状态与落盘。B审核完整语义条件及独立冻结视觉遗漏，不协调程序序列化后的碎片。不保证概率模型必然按carrier返回或语义判断必然正确。新旧journal按原身份恢复；冻结原件变化持久拒绝，不由恢复覆盖掩盖。未知原请求只观察，不重派。

## 改造前后与证明边界

| 项目 | BEFORE | AFTER |
|---|---|---|
| A_TO_B_REINTERPRETATION | B重新解释程序/模型维护的正式字符串、alias及机械关系 | B审核完整Condition及其Need语境，再由程序编译；与A独立的冻结视觉覆盖题 |
| MODEL_MAINTAINED_DUPLICATION | 模型协调技术值/alias、ID/path/hash/sidecar等重复表示 | 正式派生结构由程序拥有；A只能提交有限语义选择，非法猜测不能进正式合同 |
| ARTIFACT_DELIVERY | 模型主动write正式文件与路径 | 原run可信终态+完整assistant result，Harness核对UTF8/SHA后程序原子落盘；本轮非法结果只保留诊断，不变成正式合同 |

软件可以证明 `DETERMINISTIC_CONTRACT / REJECTION / FIXED_CORRECT_HAPPY_PATH / SEMANTIC_REGRESSION / ARTIFACT_TRANSPORT`；`REAL_MODEL` 本轮实际失败，不能合并为稳定生产能力。S2容量证明不是所有合法A都会遵循Schema的证明。本轮真实B/repair未进入，因此MAX_B_INPUT和MAX_REPAIR_INPUT均0，不冒充最大理论容量或真实复核成功。

## 本轮实时预检与运行

Gateway 2026.9.4 PID10166，CLI/daemon/config/SDK只读bridge都指向`.openclaw-easel`及main agent SQLite；新鲜RPC默认MiniMax-M3，无fallback。实时Gateway active/lost/audit0；旧Creation及十批评测原句柄pending/submitting/release0。7个真实旧作品均已达到失败额度，未恢复。另1条9月18日历史interrupted input所在session为done，与新鲜会话隔离，未冒认原run成功。只用已购文字套餐；前后同凭证只读quota认证，窗口100%→99%、周97%→97%，实际现金账单和可靠token计数UNKNOWN。

隔离冻结3开发主题各2次的6个全新Creation。只执行第0项d01，Preparation成功，A终态成功但入口拒绝；随后立即停批，其余5项不执行。132秒，Prep/A正式RPC各1，B/Truth/repair0，native阶段函数3次（A第二次读取已失败结果，不是新的RPC），assistant消息18条，不将此数字冒认独立测得的Provider HTTP请求数。独立语义正式评分未进入，失败来自结构合同入口。

## 根因与停止判断

同一A run原始结果7,849字节、`stopReason=stop`、SHA `ae7a790e686b1d6b7d4aa2004497e3aeb194a7d7a282681304d18d4645e2d7b8`，无4096截断、无传输丢失。首个错误是Markdown fenced JSON；仅诊断剥开外层后仍有多项违规：18条条件超过12上限、输出目录冒充scope、图片源时长15秒、未知continuity引用、frame/native_ratio矛盾及8项unresolved。模型又把后期文案做成独立video素材Need。程序拒绝这些结果，没有手工改正式产物、删条件、升降required或放宽准入。

`root_cause = MODEL_SEMANTIC_CARRIER_NONCONFORMANCE`。只做fence兼容不能解决该实际结果；当前问题不能无损定位到一个获准局部patch，整对象再生和放宽carrier均违反本轮边界，因此不使用可选的第二轮额度。没有达到“两轮同根因”的触发条件，不能伪称该停止阈值已经耗尽；本次依据首失败停批及缺少安全充分的targeted fix停止。第二轮NOT_EXECUTED。

下一步候选需另行设计评审：调查实际Runtime可执行的受约束结构输出，而不是继续补一句Prompt；核对A实际语义上下文中制作目录、授权状态与语义选择的边界；保留本轮原始反例验证carrier遵循与语义保真。不得借此迁移模型、升级Runtime或启动R4。

## 最终状态

```ini
PLANNING_VNEXT_IMPLEMENTATION = FAIL（软件PASS，真实Development未通过）
S1_CANONICAL_FACTS = SOFTWARE_PASS
S2_HARNESS_CAPTURE = SOFTWARE_PASS；本轮完整原结果可恢复
S3_A_NARROWING = SOFTWARE_PASS；实际模型carrier不合规
S4_BOUNDED_REVIEW = SOFTWARE_PASS；本轮未进入B
S5_INTEGRATION = SOFTWARE_PASS
ASTRA = CONTINUE（软件冻结）
DEV_EVAL = FAIL / STOP_NEW_DISPATCH
DEV_ROUNDS = 1
RUNS = 1/6
FINAL_SUCCESS = 0
CONTRACT_FAILURES = 1
SEMANTIC_FAILURES = NOT_FORMALLY_EVALUATED
REPAIRS = 0
ARTIFACT_FAILURES = 1 STRUCTURED_OUTPUT_INVALID；0 transport loss
MODEL_TRUNCATIONS = 0
STATE_VIOLATIONS = 0
SUPPLY_CALLS = 0
CALLS = Prep1/A1/B0/Truth0/repair0；RPC2
ELAPSED_TIME = 132s
MAX_B_INPUT = 0
MAX_REPAIR_INPUT = 0
COST = 文字套餐窗口约1个百分点；实际账单UNKNOWN
ENGINEERING_INTERVENTION = 0（固定真实轮次内）
HISTORICAL_FAILS_PRESERVED = YES
READY_FOR_FORMAL_R4 = NO
MATERIAL_READY = NO
BLOCKERS = MODEL_SEMANTIC_CARRIER_NONCONFORMANCE；没有安全充分的局部修复
```

本轮结束后pending/submitting/release0，Gateway active/lost/audit0，保留现场。完整脱敏transcript、Creation/Attempt/账本/配额与调用现场位于本机受保护的`Library/Application Support/Easel/acceptance/planning-vnext-development-2026-10-08-aa0ab42a`，不入Git。仓库仅保存[脱敏汇总](fixtures/planning-material-matrix-2026-10-06/vnext/development-final.json)、[真实A反例](../../tests/fixtures/planning-vnext-development-2026-10-08/round1-a-original.txt)和溯源摘要；历史文件不覆盖。
