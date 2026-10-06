# 真实 Planning 合同失败 fixture

来源：Creation `cr_94b5d27f5fb140de85981cecba009a9d` / Attempt `fa_2368857a95b3c017098064d189ce84e4`，2026-10-06 独立 Material E2E 自动失败停止时的最终两份 Planning JSON。只复制原件字节，未手改内容；与受保护运行归档的 JSON 对象完全一致（归档重新序列化，因此归档文件字节 SHA 不同）。无凭证、认证或生成媒体。

| 原始文件 | SHA-256 |
|---|---|
| MATERIAL_PLAN.json | 13085a5d247f4a7f128abdfdf813201016d070e96e08c5b43fa370067a3b1516 |
| MATERIAL_REQUIREMENTS.json | c40e165d0c30d9177dcaa8fe08552e4d2b74b91dfde9b4a8ebe2c81e4c402f59 |

原合同断口：要求文件采用身份包装和 visual_requirements 数组，混入声音 Need；路径使用 modality_spec/visual_style，空字符串代替无偏好引用，漏掉显式 preferred_visual_details；三项必要描述将冻结原文的弯单引号复制为直单引号。Plan 使用三个标量查询变体字段。完整运行证据见 `docs/acceptance/material-independent-e2e-2026-10-06.md`，原运行仍为 FAIL。

确定性回归直接读取这些字节并断言 SHA，证明 7 个视觉 Need 全部保留，8 required / 3 optional 不变、4 个声音 Need 隔离、必要原文逐字覆盖、显式软偏好不升级、异常拒绝和 consumer 不再分类。观察阶段仅使用本地确定性 PNG 与假观察响应，返回 uncertain，不构成素材准入或真实模型效果证据。
