# Content Asset 与 Material Promotion 验收

日期：2026-09-29
范围：正式 Selected Output 登记、历史 Selected Output 对账、Attempt Material Promotion 与 Rights gate。没有创建新 Creation、重新运行 AI Generation 或启动下一条 E2E。

## Selected Output → Content Library

- 在 Creation Selection 生命周期内，仅接受当前已选 Attempt、`APPROVED` Review、human/truth/style/technical 全部通过、Review 输出名与 SHA 绑定且磁盘文件 SHA 一致的 Output。
- 登记将原视频复制到 `outputs/creation-<creation-id>-<sha前缀>/final.mp4`，不移动 Attempt 原始产物。项目 `.easel.json` 和 Creation `content_asset` 保留 Creation、Attempt、Build、Selected Output、SHA、attribution、时长、分辨率、音视频 codec 和文件大小。
- 对已有 Creation 运行幂等 reconciliation：4 条有正式 Selected Output 证据的 Creation 登记成功，0 条无效；再次运行仍为 4 条，未登记未选中 Attempt 文件。
- Creation `cr_fc46c0fd949a4beca0043be745b9458d` 的视频在 `/api/outputs` 项目树可见；`/api/media/.../final.mp4` 返回 HTTP 200、`video/mp4`，响应字节 SHA 等于 Selected Output SHA `59ad3d0d7ab60673ce7cc728283add9b0de892d2d5996ca4d4d1a7e4f0eb44b3`。元数据为 10 秒、540×960、H.264/AAC。
- 内容库卡片与作品详情展示来自 Content Core 的主题、Production Brief 字幕或 Attempt Script 文案。当前真实 Creation 展示主题「给注意力一个短暂的停顿」和文案「停一下。」；其他历史作品可从绑定脚本恢复的字幕/旁白也已回填。无法取得脚本的历史 Attempt 不猜测文案，界面会明确提示未单独登记。
- 生命周期集成回归覆盖 Selection 登记、来源关联、内容字节一致及重复登记不新增条目。

## Attempt Material → Material Library

- Creator 完成页可查看本次使用素材，并对单项显式确认保存；服务端重新读取 Attempt 记录，核验身份和 SHA、技术检查、来源/获取证据、Rights 许可及 attribution 条件后才写入 Library。
- Catalog 保留原 `MaterialAsset` identity 和完整事实，并记录来源 Creation/Attempt、acquisition provenance、generation lineage 及 Promotion consent。`UNKNOWN`、`RESTRICTED`、缺少 Rights evidence、缺少 KNOWN license name、缺少必要 attribution text 均拒绝 Promotion。
- Fixture 端到端回归验证一项素材通过显式 Promotion 后进入 scope 内 Library，并由既有 Library-first reuse 路径作为后续 Creation 候选；Rights UNKNOWN/RESTRICTED 拒绝回归通过。
- 当前真实 Creation 的一项 Pexels 视频素材在只读资格检查中为 `KNOWN`、技术检查通过、证据完整且符合 Promotion 条件。它仍未写入 Material Library；Creator/Operator 尚未对该具体素材作出保存选择。其余两个 Attempt 素材也未自动保存。

## 验证

- `.venv/bin/python -m pytest -q tests/test_material_library.py tests/test_material_library_reuse.py tests/test_material_p1_regression.py tests/test_hypit_integration.py`：42 passed。
- `cd web/frontend && npm run lint && npm run build`：通过；lint 仅报告既有 `AccountsPage.tsx` hook dependency 警告。
- `.venv/bin/python -m compileall -q easel web/app.py`、`git diff --check`：通过。
