"""Versioned natural-expression instructions; no model call or style classifier.

Original, project-specific wording informed by the reviewed principles in
docs/mainline/architecture/contracts.md §6.1.5 (Humanizer, Humanizer-zh, Stop Slop).
Snapshots come only from trusted creation/Plan storage, never model output.
"""
from copy import deepcopy
import hashlib
import json
from typing import Literal

from .errors import ProductionError

ExpressionRole = Literal['write', 'visual', 'review']
# Format version; wording revisions are identified by the frozen digest.
VERSION = 'natural-expression-4'
RULES = {
    'core': (
        '结合本期内容、六维画像、频道和导演作具体选择：画像提供身份、表达偏好、受众关系、平台、边界和已确认经验；'
        '频道细化本次交流语境；导演决定叙事及视听方法；本期输入决定当前问题与拟表达观点。'
        '不使用一条总优先级覆盖全部依据：本片声音/字幕等按已解析设置执行，继承默认不冒称用户逐项确认，导演不覆盖；'
        '事实矛盾保留来源及用户纠正，关键冲突在原方案确认中说明；风格取舍结合本期目的，不另造人设。'
        '正式、轻松、诗性均可，不强制聊天、幽默或电影化。采用的事实、数字、引用、观点、因果、否定、条件与不确定程度不失真；材料不必逐项进入旁白。'
        '不编造亲历、感受或身份，不迁移参考作品经历；虚构仅限本次明确虚构语境。'
        '来源、核验程度与表达性质分别说明：用户提供也可能待核实，个人理解可以有资料支持但不是原作者原意；'
        '放入facts不等于核验，拟议core_views不等于作者已认可。缺原文或工具时如实说明，不虚构查证。'
        '自然化不扩大权限、不改冻结内容或绕过Rights及声音保护；单片反馈不自动写入长期画像、频道或导演。'
    ),
    'write': (
        '用户只给一句感悟或问题，也应基于现有材料主动展开、挑战和提出方案，不要求先交完整稿。'
        'summary简述本期讨论重点、必要背景和所选导演的具体处理，不复述全套配置；'
        'core_views表达拟议判断，facts保留来源和核验说明，scene.purpose说明本段作用，visual说明实现及替代范围。'
        '依本期目的、作者表达和导演方法取舍材料、组织推进，不固定结构或平均展开；保留明确必用内容、必要依据、真实矛盾与未解问题。'
        '口播适合实际说出，指代清楚、意思衔接；保留有作用的重复、术语、具体判断与作者语气，不用空泛总结、口头禅或拆短句代替表达。'
        '有旁白时，在规划内完成语义分组、情绪与停顿取舍，不交给配音或剪辑阶段再设计。'
        '连续口播用narration_policy.groups记录完整思路，稳定id与scene_ids按顺序覆盖有声场景；一个完整思路可只用一组，也可跨镜头，不按句数或场景数凑组。'
        '逐组在emotion_reason说明具体内容、讲述意图及情绪取舍；选择模型支持的情绪时写入emotion，选择默认表达时留空，不把描述冒充已传参。'
        '从当前模型支持值选择贴合内容的表达；平静克制也可明确选calm，不把“不夸张”当作不设计。不要将稿中谈论的焦虑机械对应fearful或sad，也不为凑变化强行切换情绪。'
        '按内容和固定声音约束决定是否指定模型支持的emotion；null表示继承已固定全局情绪，若无全局情绪则使用供应商默认，不声称传入了具体情绪。不强制选择或切换情绪。仅有必要且当前配音支持时填写narration_pauses，其余为空。'
        '在相关scene.purpose/visual简述所选讲述推进与声音取舍，包括为何自然连说或沿用默认；不逐句标注，不把导演说明念入口播，不覆盖固定音色、语速及受保护原声。'
        '材料的使用边界约束可写内容，不必逐项念出；影响听众判断的条件与不确定性须在表达中保留。'
        'scene.purpose与visual需对应：画面可解释、举证、营造环境或情绪；需要证据处保留证据要求，其余可用获准替代表达，示意不冒充事实证据。'
        '拟议画面与已取得素材分开表述，未观察的连续性不作保证；替代不得改变必要事实、动作或明确要求。'
        '在本次生成内核对全文信息推进、事实条件及脚本与场景旁白一致；导演注释不进入TTS，不输出检查过程，不加独立润色调用。'
    ),
    'visual': (
        '依据冻结本期方向和scene.purpose落实导演意图，决定取段与镜头关系，不按关键词逐句凑图。'
        '区分拟议visual、素材元数据与实际观察；未观察区间、同一现场或同一人物的连续性不得臆测。'
        '画面承担解释、证据、环境或情绪要与场景目的相符；示意不冒充证据，必要操作和关键动作不能省略。'
        '实际剪辑依据实测音轨、可靠字幕锚点及素材可用区间安排切点，一个镜头可跨多句；'
        '按内容、动作、情绪及观看需要决定切换与停留，保留有表达目的的快切、长镜头、重复和留白，不预设统一节奏、不堆无作用的装饰。'
        '在符合画意的候选中优先清晰准确对焦的源片，裁切预留源分辨率，不以锐化光晕代替清晰度。'
        '候选声音角色与技术测量不等于实际试听认可；缺关键证据说明局限。'
        '只在适配许可及本轮修订范围内编辑；不能为自然度改冻结口播、音色、字幕时码或受保护原声。'
    ),
    'review': (
        '结合本期方向、作者依据和导演意图，核对实际收到的文字、画面或声音。'
        '检查全文信息是否推进、条件与依据是否保留，不只修开头结尾；无编号、短句多或通顺不代表表达已自然。'
        '核对场景目的与具体实现是否相符，环境或情绪画面无需强行举证；未取得素材时只评价方案，不假称执行成立。'
        '旁白的分组、情绪与停顿是规划职责，核对已有groups、narration_pauses与purpose/visual是否落实本期声音意图；不能把缺失设计建议推到执行阶段。'
        '逐组核对emotion_reason与本组内容、emotion和固定声音约束是否一致；null可表示无额外情绪参数，不等同于已传具体情绪。单组、默认表达、同一情绪和空停顿均可成立，不按数量判优劣；实际听感留待配音后验证。'
        'findings指出具体句段或时间、实际证据、受损的事实/理解/明确要求及应修正的层；'
        '具体缺陷不得藏入建议，另一种合理表达放suggestions，未见未听和观察范围放limitations。'
        '套话或机械节奏仅是线索，笼统像AI或没有电影感不直接触发返工，不打去AI分数。'
        '不把稿件当听过配音，不把抽帧当连续音画检查；作品接受、导演接受和长期保存各自需要明确依据。'
    ),
}


def _digest(version, rules):
    return hashlib.sha256(json.dumps({'version': version, 'rules': rules},
        sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def snapshot() -> dict:
    rules = deepcopy(RULES)
    return {'version': VERSION, 'digest': _digest(VERSION, rules), 'rules': rules}


def validate(policy) -> dict:
    # Keep frozen rule content, but execute only the current format.
    # The digest detects corruption; provenance is enforced by creation/freeze.
    if not policy:
        raise ProductionError('expression_policy_missing',
            '此任务缺少新任务的自然表达规则快照，不属于本期支持范围；旧成果已保留，请新建方案。',
            requires_decision=True)
    if (not isinstance(policy, dict) or set(policy) != {'version', 'digest', 'rules'}
            or not isinstance(policy['version'], str) or not 1 <= len(policy['version']) <= 100
            or not isinstance(policy['rules'], dict) or set(policy['rules']) != {'core', 'write', 'visual', 'review'}
            or any(not isinstance(v, str) or not 1 <= len(v) <= 8000 for v in policy['rules'].values())
            or policy['digest'] != _digest(policy['version'], policy['rules'])):
        raise ProductionError('expression_policy_invalid',
            '自然表达规则快照无效，已停止执行并保留原任务，未自动替换规则。', requires_decision=True)
    if policy['version'] != VERSION:
        raise ProductionError('expression_policy_unsupported',
            '此任务的规则版本不受当前V2.1执行路径支持；历史成果保留，请重新规划。', requires_decision=True)
    return deepcopy(policy)


def instructions(policy, role: ExpressionRole) -> str:
    if role not in ('write', 'visual', 'review'):
        raise ValueError('Unknown expression role')
    saved = validate(policy)
    return '\n' + saved['rules']['core'] + '\n' + saved['rules'][role]
