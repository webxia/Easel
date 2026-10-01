# AI 素材生成

状态：MiniMax Image / Video / 预置音色 TTS 已接入 Material Layer，并有隔离输出的技术验收；操作台已提供素材级 Rights 事实录入与 Gate 重算，真实 Creation/Production 使用尚未完成验收。潜在计费生成需明确授权；新委托可按已批准总预算与服务范围复用授权，逐次执行仍核价和占额，未知或越界则停止。见 [ADR-004 授权澄清](../decisions/ADR-004-material-layer-v1.3-baseline.md)。详见 [T09A](../tasks/v1c-t09-minimax-video.md)、[软件验收](../acceptance/minimax-image-speech-software-2026-09-28.md) 和[隔离输出记录](../acceptance/minimax-image-speech-smoke-2026-09-28.md)。

```text
冻结 Content / Script + MaterialPlan
→ Material Layer：Library / Local / 外部来源优先
→ 明确授权范围内，核价并按 Need 调用 MiniMax Adapter
→ Attempt 内记录结果并进入普通 Inspect / Rights / Match / Bundle / Readiness
→ Production 明确选材
→ Hypit 本地 CLI 剪辑、混音与渲染
→ Easel 导出检查、审片、选定输出
```

Material Layer 决定是否生成并拥有 Provider Adapter、生成记录和素材准入；MiniMax schema 不进入 Material Domain。Hypit 仅负责制作，不生成供制作使用的 AI 媒体。TTS 使用冻结脚本与预置音色，不克隆真人声音。

## 当前闭环与剩余验证

- 三种模态的软件 Adapter 和独立真实输出 intake 已验收；生成记录绑定 Attempt、Plan revision、Need，结果通过普通 Gate。
- 供给重算会恢复与当前 Attempt、Plan revision、Need 匹配且技术检查通过的已完成生成资产。操作员可在制作操作台对 SHA 匹配的生成素材提交 Rights 事实并重算同一 Gate；系统不推断许可，UNKNOWN 仍阻断 required Need。
- 新委托的预置旁白已接入有限用途自动判断：同时核对已确认文字授权、当前请求/账号范围/系统音色、已评估的协议版本、冻结脚本及独立声音内容证据后，按 KNOWN + 本作品内部制作使用；不是依据 Provider 名称或付费成功放行。使用范围随成片保存并限制发布，素材库不允许跨作品复用。协议或证据不满足条件、图片/视频输出仍保留未知状态；真实感知效果与整体自主交付尚未验收。
- 尚未证明生成素材在真实 Creation 中经 Rights 审核、Production 选材并完成 Hypit Build。该闭环和整个 V1 的新鲜 E2E 进入 [T15](../tasks/v1c-t15-e2e-readiness.md)。
- 不支持的参考图、场景级 TTS 与声音克隆能力必须显式拒绝；不创建第二条视频主链。

Hypit Generation 历史路线及旧 Acceptance 只作决策背景，不是当前产品入口。当前唯一状态汇总见 [02_CURRENT_STATE](../02_CURRENT_STATE.md)。
