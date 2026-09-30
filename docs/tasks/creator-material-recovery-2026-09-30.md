# Creator 素材缺口恢复

状态：软件修复与同一 Creation 的素材阶段恢复完成；成片 E2E 尚未完成。用户授权先修复根因，再继续同一个 Creation；本次现有旁白明确允许使用，无需再次确认或生成。

根因：Planning 将真实授权素材误收窄为特定来源，长镜头说明直接变成检索词；素材 NOT_READY 后没有正式来源修订/补料入口，重跑 Supply 又丢弃既有素材集合。

范围：制作开始前，正常作品区提供一次有身份绑定、幂等留痕的素材恢复操作。仅允许明确选择扩展配乐来源及修改检索提示；保留脚本、场景、Director、冻结 Handoff 和生成音频。复用字节核验通过的素材，只检索未覆盖需求；不调用生成、不提交 Build。脚本、规格和场景修改不在本次范围。

边界：不更改 Material V1.3 Domain；来源修订记录旧/新 Plan revision 和原 Bundle checkpoint，重新计算 Match/Rights/Readiness，不升级未知权利或伪造语义证据。已执行/批准制作时拒绝该恢复。付费生成批准不能复用到新生成。用户本次旁白指示通过既有正式 Rights 复核记录为素材级许可声明，不当作第三方条款保证。

依赖与顺序：检索提示合同及保留素材 Supply → 正式素材恢复入口及 revision 身份/幂等性 → 普通作品区动作 → 确定性跨模块验证 → 同一 Creation 阶段重放。

验收：恢复不丢既有 Asset/证据、不重新请求已覆盖需求、不调用付费生成；过期身份与已进入制作的状态阻断；相同请求复用结果；旁白脚本哈希与生成历史保留；重新 Match/Readiness 仍阻断不合格/未知许可素材。真实验收只使用现有一个 Creation。


追加根因：生成旁白没有可用语义证据；原匹配复核只支持视觉，Creator 已试听通过的结论无法进入 Gate，已获许可音频反而被 UI 误报为缺失。复用既有素材/SHA 复核入口支持脚本绑定旁白及配乐试听，未知 Rights 和署名缺口独立阻断。普通 Rights 卡只列实际待处理素材，不重复复核已准入许可。

验证：127 项 Preparation/Material/生成/制作边界测试通过；随后音频审核与来源修订最终增量的 Material/Compiler/Rights/敏感接口组合 52 passed（28 deselected）。前端 lint/build、compileall、技能合同验证、diff check 通过。回归覆盖同请求复用、Supply 已完成但 Gate 更新中断时对账、旁白脚本身份错配拒绝、音频试听不能清除 Rights/署名阻断、父 SupplyRun 链接和原素材保留。

实际阶段重放：仅现有 Creation `cr_046bb34c26a7444f9fd335c991ec1cc4`。记录 Creator 当前旁白使用声明及已给出的试听结论；旁白不再阻断。普通补料入口运行完成，原 7 个 Asset 全部保留，当前 38 个 Asset，生成记录仍为 1 次。剩余 5 个视觉 Need 与 1 个配乐 Need 待核对。没有新 TTS、Authoring、Plan、Build、最终输出或入库；不宣称本轮 Creator E2E 通过。
