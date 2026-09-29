# MiniMax Image / Voice 软件验收

日期：2026-09-28
状态：**SOFTWARE_ACCEPTED；Image / Voice 另有隔离真实冒烟证据**

## 范围

- Image-01：按 MiniMax 官方契约请求 base64 图片字节，直接写入 Attempt；尺寸、格式和 SHA 由现有 Technical Inspector 检查。
- T2A：将已通过 Truth review 的冻结 `planning/SCRIPT.md` 按 Global Voice Need 中的 SHA-256 绑定，使用配置的预置音色返回 MP3 字节；不调用声音克隆或场景文本切片。
- 图片与语音都记录 Provider/model、Need、Attempt、Plan revision、输入摘要、显式付费确认事实和输出身份，随后通过普通 Material Gate。Rights 默认 `UNKNOWN`。
- 操作台复用当前阻塞 Need 和本机 Operator 身份验证；用户逐次确认潜在费用。真实调用和限制见[多模态冒烟记录](minimax-image-speech-smoke-2026-09-28.md)。

## 验证

- MiniMax Image/Speech 与 Video、Material intake/Store、Runtime config、Rights/Readiness/Router/Inspector 定向套件：**81 passed**。
- 按真实响应修正 Image-01 `image_base64` 数组解析后，MiniMax Image/Speech 定向套件：**5 passed**；修复后的真实图片输出见[隔离冒烟记录](minimax-image-speech-smoke-2026-09-28.md)。
- 后端全量测试：**458 passed, 5 skipped**（补入 MiniMax 付费路由的操作员认证回归）。
- `compileall`、`git diff --check`、前端 lint/build 通过。lint 有一个既存 `AccountsPage.tsx` hook 依赖警告，与本能力无关。
- 官方接口契约：[Image-01 文生图](https://platform.minimaxi.com/docs/guides/image-generation)、[T2A HTTP](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)。

该验收证明 Adapter、代码边界和确定性 Material intake。真实冒烟只覆盖具名记录中的隔离输出；不证明权利许可、真实 Creation 可用或最终配音效果。
