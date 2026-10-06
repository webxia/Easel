# 第二次独立 Material E2E：声音参数模态污染

来源：`cr_223021d92de643f0a35faea2907de7ed` / `fa_d5e99b227faa224b82f5347174850a1b`，2026-10-06，固定版本 c9cb4b9c。原始脱敏运行归档位于本机 Acceptance 目录，原现场只读保留 FAIL。

以下为实际公开 Planning 产物原字节，无人工修正、凭证、个人联系方式或运行日志：

| 文件 | 实际阶段 | SHA256 |
|---|---|---|
| MATERIAL_PLAN_OBJECT.json | Domain 已通过、扁平化之前的中间版本；10个Need均复制voice_delivery对象 | b347ba43209dafb9b04b0420aae4317dac04cca1a5b27739f6f70b730b102b3e |
| MATERIAL_PLAN.json | 最终失败版本；10个Need均包含3个扁平声音别名 | eacacfca9ed6a8d68f470f48c5812b0c32960cbb4bcce39174561f649432fd8f |
| MATERIAL_REQUIREMENTS.json | 最终要求文件，包含7视觉、无audio | d6b6a7a6880a151c45bd9e6b94dc23faf4b6e1f8c5549d1253ccad9c406061f5 |

初始版本另有Voice文稿引用/摘要配对错误，未冒充本目录的中间版本。完整版本序列保留在原本机归档。

负例要求确定性拒绝污染，不删除要求、不降级importance。合法混合对照只在测试内显式构造：移除错误跨模态副本、将Voice上的三个值放回既有canonical对象；仅证明校验/consumer职责与异步单次修复身份，不构成对真实产物的自动修正，也不宣称真实MATERIAL_READY。真实JSON字节不改动。
