# V1 素材能力迁入记录

源仓库仅只读：`/Users/xgx/Projects/Easel-V1-Archive`，固定提交 `57c8e2ade21af9fb6abccdab3f7ba8e50132314f`。原仓库 `LICENSE` 为 Apache-2.0；本仓库同许可证，迁入文件保留来源与改动声明。本次只读源码与测试，不读取或迁移用户素材库、Profile、Attempt、凭证或历史运行数据。

| 能力 | 固定 V1 源文件（相对仓库） | V2 实际落点与适配 |
| --- | --- | --- |
| M01 素材、来源、权益、技术/语义合同 | `easel/materials/domain/models.py` | `domain/models.py`；保留相关 Pydantic 类型，删除 MaterialPlan/Bundle/Readiness/SupplyRun 与旧生产状态 |
| M01 内容寻址、摘要核验、安全定位 | `easel/materials/store.py`、`library.py` | `store.py`、`library.py`；临时文件先验摘要再原子发布，保留路径/symlink/同内容去重；旧 catalog 不自动升级 |
| M01 库可见范围、显式提升、引用 | `easel/materials/library.py` | `LibraryVisibility(owner_id, profile_ref)` 与 `UseContext(work_id,purpose)`；同画像跨作品仍要求显式提升，无画像/仅本片/参考用途不自动扩权；引用先保留，合法释放后方可回收 |
| M02 元数据/语义检索、索引失效 | `easel/materials/semantic_index.py`、`application/library_reuse.py` | 同名新模块；索引不作权限依据，读取实际 catalog 再检查用途、摘要和 Rights；缺模型/过期索引明确 METADATA_FALLBACK；同片重用不沿用旧 already_used 排除 |
| M02/M03 技术检查与去重 | `application/inspector.py`、`application/dedup.py` | 实际 Pillow/ffprobe、原哈希/近重复与候选多样性算法；不把排序当导演选择 |
| M03 来源和使用权资格 | `application/rights.py`、`providers/pexels.py` | `application/rights.py`、`production/providers/stock.py`；保留素材专属证据、限制与准确署名；公开 URL 不等于授权，许可未知/限制冲突阻止剪入 |
| M04 外部下载与有限回退 | `application/acquisition.py`、`application/library_first.py` | `application/acquisition.py`、`supply.py`；实际 DNS 固定 TLS、逐跳验证、有限次数/大小、损坏媒体检查；库优先、外部回退、仅返回缺口与生成建议，不在检索内部收费生成 |
| M05 IMAGE/VIDEO 协议子集 | `providers/minimax_image.py`、`providers/minimax_video.py` | `production/providers/generation_http.py`；新 OperationService 统一准入；MiniMax image-01 同步本地回执、MiniMax H3/H3-Max 异步提交/单次查询/下载分离。没有旧 confirmed_paid、报价、阶段 budget 或无限轮询 |
| V2 实际主线 | 不直接复制旧 orchestration | `production/materials.py`、`production/supply_tasks.py`；已确认 Plan + work_inputs → 合格候选 → 作品资产 IDs → edit；必用/参考不混用，缺口由模型在已授权能力内决定，操作与产物恢复不重发 |

## 外部协议依据

实施时（2026-10-17）核对官方 [MiniMax 生图](https://platform.minimax.io/docs/api-reference/image-generation-t2i)、[视频创建](https://platform.minimax.io/docs/api-reference/video-generation-v2-create)、[视频查询](https://platform.minimax.io/docs/api-reference/video-generation-v2-query) 与 [Pexels License](https://www.pexels.com/license/)。Pexels API 文档页面未成功抓取，HTTP search 端点/字段迁自固定 V1 实现并经 MockTransport 合同测试；不冒充真实服务验证。

- IMAGE：`POST /v1/image_generation`，`image-01`，base64 返回；本地原子保存图片与私有回执后返回成功。同请求标识只读原回执；本地回执缺失只能 unknown，不等于远端从未提交。
- VIDEO：`POST /v2/video_generation` 后 `GET /v2/query/video_generation/<task_id>`。H3 明确 4～15 秒/768P 或 2K，H3-Max 明确 5～15 秒/480P 或 768P；不静默替换模型、分辨率或时长。长成片由已确认剪辑方案组织素材，不把单次生成长度当成作品时长上限。
- 供应商的 key、签名下载链接、私有请求/回执不进入事件或公开 task result。HTTP 5xx、超时、身份不匹配、无法核实查询均不授权重发。
- 下载仅信任显式供应商 host allowlist，连接经验证的公网 IP，重定向每跳重新校验；禁止 HTTP、凭证 URL、私网/混合 DNS、越界端口和无限回退。

## 配置与权利证据

`configured_supply(service, operations, planning, settings)` 只构造适配器，不调用服务或授予权限。自动补料必须先有实际可尝试的外部来源；缺配置时明确阻塞，不说成检索无结果。用户明确选择生成的请求仍须通过本次授权、额度和 Rights。主线配置源继续由 `read_settings` 管理；本模块不另读环境或用户凭证文件。

| 配置 | 行为 |
| --- | --- |
| `PEXELS_API_KEY` | 有值才构造 Pexels 图片/视频检索；许可规则来自上述证据，不发送该 key 到素材 CDN |
| `MINIMAX_API_KEY` | 有值才构造 MiniMax 适配器，实际发送仍检查本片方案授权/模式/剩余次数 |
| `EASEL_IMAGE_MODEL` | 仅支持 `image-01`；省略时适配器声明此型号，不代表已授权调用 |
| `EASEL_VIDEO_MODEL` | 必须显式为 `MiniMax-H3` 或 `MiniMax-H3-Max`，省略/不支持时 VIDEO 不可用 |
| `EASEL_GENERATION_RIGHTS_JSON` | JSON 文本或绝对本地 JSON 文件路径；最多 256 KiB，`schema_version:1`，可含 `IMAGE`、`VIDEO` 两个 `RightsInfo` 对象。缺失、无效、许可未知或证据缺失均不把该模态展示为可用 |

RightsInfo 使用实际确认的 `status`、`license_name`、`license_url`、`evidence`（`kind/reference/observed_at/summary`）、`usage_constraints`、署名要求。不要抄写示例许可或用有 key 代替权利证据。只有成功回执后才补充 `asset_generation_receipt`，该事实不替代供应商许可本身。`supply_capabilities` 只公开服务身份、模态和就绪状态。

上传输入同样保留 `work_inputs.metadata.source.rights`。没有用户明确的素材许可依据时保留未知，不擅自写“用户上传所以可任意使用”。参考媒体不会作为剪辑候选；必用媒体有问题时阻塞并标出 input ID，不能由图库或 AI 偷换。

## 运行与恢复界限

素材文件复制到 `outputs/works/<work_id>/assets/`，生产域 artifacts 登记在 `ctx.transaction()` 所有权守卫内，包含 input ID、source、rights、attribution；交给 edit 的 payload 仅 `schema_version` 与 `asset_ids`。素材是依赖叶子，剪辑/产物将引用这些 ID。署名字段为 JSON 结构，主线导出负责把选中素材的署名实际交给用户。

库引用与生产域处于两个数据库：先保守保留 `reference_id=artifact_id`，后进行复制/生产域登记；崩溃可留下待核对的保留引用，不能留下可被清理的在用文件。作品/版本合法删除后可按本作品作用域释放对应引用；输入引用另行保留。`collect_deleted()` 只回收已明确 tombstone 且无引用、无其他活记录共享的对象，不扫描上传目录、旧库或其他用户文件。

## 验证范围

本机 Python 3.12、Pillow、FFmpeg/ffprobe，全部在 pytest 临时目录与离线 `httpx.MockTransport` 中执行。测试移植保留 V1 权益、去重、库检索的负例意图，并增加 V2 可见性、参考/必用、版本引用保护、陈旧索引、未知回执不重发及实际 Store 主线衔接。

真实 Pexels/MiniMax 服务、真实素材相关性、模型创作品质、生成自然度、语义 embedding 服务和 Ubuntu/Windows 仍 **NOT_TESTED**；没有付费调用。实际测试命令/结果记录在 S6-06/07 卡；整体成片与 Creator 接受不由素材测试代替。
