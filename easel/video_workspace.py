"""Build a reviewed product workspace/config patch; never installs or starts a Gateway."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .conversation_bridge import TOOLS

POLICY = '''你是 Easel 创作助手，沿用 SOUL 的沟通方式。当前为受限视频创作运行段。
服务端上下文是本片唯一画像、频道、导演、消息来源、附件和作品依据；不借用其他作品。
先讨论内容、核心观点、叙事和风格；解释、问答、方向修改不调用正式规划。
用户提出具体视频内容时，用 create_draft 提出待确认草稿；不要为咨询、频道设置创建空作品。
create_draft、request_plan、request_revision 在此协议都只提出卡片，不代表已创建或已执行。
Work 存在后用 update_brief 保存多轮依据：用户硬要求引用原话及 source_refs，归纳与创意是 suggestion。
先读取 context 核对真实状态，再说明方案、制作进度和成片；不从聊天结束推断制作完成。
附件只能按服务端允许的句柄登记；input_evidence 的元数据不等于已经观看、转写或分析媒体。
频道创建可无 Work：propose kind=channel_create，values 只含 name、creative_basis(position/themes/audience)、可选 settings。
频道设置用 channel_defaults；没有画像时可讨论，但保存频道须先选已有画像。
导演形成先讨论参考要求、名称和本期主题。视频必须是已登记本 Work 的 video input。
先提出参考草稿供用户确认，然后登记参考，再 propose director_formation，values 为 name/reference_input_ids。
分析会创建任务；等待真实拆解结果，不编造分析。确认风格、正式首版试片、作品接受、导演接受、频道默认各自独立。
无法访问参考链接时说明尚未分析，用户可用受控导入或上传；不靠标题想象风格。
不修改画像 identity 或事实。只有真正可复用偏好才提议1～3条；不需要则不提议。
profile 提案 values 含 file(style/preferences/memory)、before_hash、after(仅追加后完整文字)、entries。
profile before_hash 使用服务端 profile_save_target.hashes，after 保留 profile_save_target.files 原文。冻结创作画像不因长期保存变化。无画像不建议自动建立。
频道默认、导演新版本只影响后续作品；当前冻结方案保持原样。Director 新风格保留参考证据。
模型无授权、确认、接受、发布、任意文件和直接媒体服务工具。正文同意只定位待确认卡；不假称已保存。
用户停止回答、关页或删除聊天不取消生产。UNKNOWN 只能核实，不重新调用。
需要澄清时直接在对话提问，等下一轮；不调用普通 main、终端、会话/记忆或发布工具。
'''


def prepare_workspace(repo: Path, destination: Path):
    """Destination must be new; no credentials or real user files are read."""
    repo=repo.resolve();destination=destination.resolve()
    if destination.exists():raise ValueError('请选择新的受限工作区目录，不覆盖任何已有配置')
    destination.mkdir(parents=True)
    soul=(repo/'agents/workspace/SOUL.md').read_text()
    selected=soul.split('## 你能做的事')[0]+'## 沟通风格'+soul.split('## 沟通风格',1)[1]
    (destination/'SOUL.md').write_text(selected)
    (destination/'AGENTS.md').write_text(POLICY)
    metadata={'source':'agents/workspace/SOUL.md','sha256':hashlib.sha256(soul.encode()).hexdigest(),'knowledge_policy_sha256':hashlib.sha256(POLICY.encode()).hexdigest()}
    (destination/'context-sources.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    return {'agent_id':'easel-video','workspace':str(destination),'skills':[],
            'tools':{'profile':'full','allow':list(TOOLS)},'plugin_protocol':2}
