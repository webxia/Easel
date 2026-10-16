# Easel V2 · 目标架构骨架

状态：**TARGET / DESIGN PRINCIPLES — 非实施证明**。此文件只定义当前已认可的职责和工程边界，不预先冻结 Scene Schema、SQLite 表、调度框架、Prompt 或调用批次数。

## 面向作品的主链

`Web Creation / Creator 确认 → Creative Planning → Material 供应与 Director 取舍 → 视频制作 / Hypit → Quality → Creator Review`

- **Creator / Creative Domain**：Creator/Profile、Content、Director/Creative Mode、已确认创作语义与授权范围；负责确定不可静默修改的内容，以及合法导演自由度。
- **Model / Context**：为规划、审查等不同语义任务提供必要的完整上下文；程序管理权威版本与依赖，模型不自行创造工程身份或成本授权。
- **Production Ownership**：每条新作品仅有一个有效生产执行 Owner；保存任务、调用身份、真实结果与预算，避免 UNKNOWN 重派和多状态来源相互覆盖。
- **Material Capability**：根据当前被采用方案搜索、观察、生成/复用、核查来源与 Rights、匹配素材。消费导演选择，不拥有导演权。
- **Production / Hypit**：在有资格的实际素材与确认约束下进行剪辑、时间线、音轨、构建、输出和检查。是否沿用现有模块及如何集成，需基于官方最新源码审计。
- **Review / Quality**：确认可播放性、音画和内容质量，提供可审阅版本与反馈；MP4 存在不等于用户已接受。

## 必须保持的约束

1. **确认事实与实现选项分开**。用户硬要求不能被模型自行改写；Director 可以在受委托范围内合法适配。
2. **明确输入、输出、Owner 与责任**。一个组件不能在下游静默发明上游未授权的要求。
3. **失败结果可留证、可恢复**。调用与任务是不同对象；原始回执、文件、版本与依赖可追踪。
4. **业务 Gate 有明确用途**。Rights、授权、真实输入等必须严守；不因 Prompt 不稳定而不断增加重叠的抽象 Gate。
5. **质量与效率同时优化**。重复模型调用应减少，审核应与实际业务义务相称；不能少审核即宣称可靠。
6. **复用优先、可变更**。保留官方合理模块；旧二开接口只用作参考。正式设计可通过新决定修订，不被旧字段绑死。

## 当前不冻结的设计

- `ConfirmedCreativeSpec` 的字段和旧 Proposal 的转化方式；
- Beat / Scene / Shot 的确切 Schema 与版本迁移；
- ModelGateway 具体 Provider/Agent 选型、输出形式和缓存键；
- Production Kernel 的存储、任务图和调度机制；
- Material 接口版本、剪辑编译器与质量细则。

这些应进入未来的任务和必要 ADR，经源码审计、设计评估与真实产品实验后确定。

## 变更策略

- 修改长期职责或权利边界：从需求/现有验证出发，记录必要 ADR 和替代关系，再修改代码与受影响的工程校验。
- 修局部实现缺陷：一般不要求 ADR；记录问题、预期行为、测试和真实结果即可。
- 要求保留的仅是业务不变量，**不是每个旧架构版本和旧流程名字**。
