---
name: hypit-authoring
description: "为已冻结的 Easel × Hypit Creation 编写 Treatment、Script、Scene 与 SVML/SVRun。只用于 AUTO_AUTHORING_V1；不执行媒体生成、Runtime 配置、plan、pricing、build 或发布。"
layer: produce
---

# Hypit Film Authoring

这个 Skill 只服务已经由 Easel Preparation 冻结的作品。Easel main Agent 仍是唯一 Director；本 Skill 不定义主题、观点或固定叙事模板，只将冻结的创作意图写成可验证的 Hypit 电影工程。

## 先读的输入

在任务提供的隔离 workspace 中依次阅读：

1. `AUTHORING_TASK.md`
2. `handoff/content-core.json`
3. `handoff/truth-packet.json`
4. `handoff/creator-context.json`
5. `handoff/creative-mode/` 下的 Director Treatment、视觉、声音、剪辑与 QC 文件

它们是冻结输入。不得修改、替换、补造或将它们重新解释成用户亲历。

## 固定输出位置

只在任务指定 workspace 写入：

```text
productions/easel-authoring/TREATMENT.md
productions/easel-authoring/SCRIPT.md
productions/easel-authoring/SCENES.md
productions/easel-authoring/authors/main.svml
productions/easel-authoring/runs/main.svrun
```

Treatment 说明作品的观察、情绪推进、画面与声音关系；Script 给出可自然朗读的旁白；Scenes 写清人物、环境、动作和画面职责。它们必须服务当前 Content Core，而不是套用固定三幕、固定镜头数或“过去—现在—未来”模板。

SVML/SVRun 必须是 Hypit 可以静态解析的最小完整工程。优先从本机 Hypit 已安装 examples 中理解语法；不要虚构 package 名称、Provider、模型或媒体资产。

## 绝对边界

- 不运行 `hypit plan`、`pricing`、`build`、`doctor`、`runtime`、`auth`。
- 不调用图片、视频、配音、音乐或任何其他媒体 Provider。
- SVML/SVRun 只能引用 Material Layer 已准入的素材；不得导入 Hypit 图像、视频、语音生成组件，也不得引用未选中的外部媒体。
- 不创建新的 Easel Creation、Handoff 或 Attempt。
- 不修改 `handoff/`、不写入 secret、不会公开发布。
- 不把模型推理改称用户亲历，不虚构真实职场事件、人物、数字、日期或结果。

完成后只允许运行一次静态校验：

```bash
hypit check productions/easel-authoring/runs/main.svrun --workspace "$WORKSPACE" --json
```

静态校验失败时，先修复 Authoring 文件；不要以 Runtime 或模型调用来绕过问题。
