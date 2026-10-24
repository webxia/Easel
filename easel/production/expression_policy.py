"""Versioned natural-expression instructions; no model call or style classifier.

Original, project-specific wording informed by the reviewed principles in
docs/v2/15_IMPLEMENTATION_DESIGN.md §6.1.5 (Humanizer, Humanizer-zh, Stop Slop).
Snapshots come only from trusted creation/Plan storage, never model output.
"""
from copy import deepcopy
import hashlib
import json
from typing import Literal

from .errors import ProductionError

ExpressionRole = Literal['write', 'visual', 'review']
VERSION = 'natural-expression-2'
RULES = {
    'core': (
        '自然表达通用要求：让当前内容自然、可信、容易理解，结合本次画像、频道和导演风格，保留作者判断。'
        '正式分析、轻松讲述、诗性表达均可，不强制聊天、幽默、煽情或电影式开头。'
        '保留事实、数字、引用、观点、因果、否定、条件与不确定程度，不把可能写成必然，不省掉必要推理。'
        '不编造亲历、感受或身份，不把风格参考的经历移植给作者；虚构情节须符合本次虚构创作语境。'
        '自然化不能扩大授权、改写已冻结内容或绕过事实、素材权益及声音保护。'
    ),
    'write': (
        '写作：从当前内容有意义的具体问题、观察或例子进入，避免空泛铺垫、概念堆叠、重复总结和强行升华。'
        '保留必要术语、有意重复与符合文体的句式；不靠禁词表机械替换，已经清楚的内容可以不改。'
        '先想清本段要向听众说明哪个问题，再写可一口说出的意思单元；长短句随推理变化，转折说出真实原因。'
        '避免每段都用总结句收尾、连续对称排比或只替换口语词；保留有信息的细节、立场和必要术语。'
        '提交前在本次写稿内按说话顺序检查指代、呼吸位置和拗口长句，不输出润色过程、不增加独立润色调用。'
        '口播先写得能自然说出来，按意思组织短句、转折与轻重停顿，不刻意塞入嗯啊或每句都强调。'
        '吐槽、自嘲仅在人物和语境适合时使用，不制造虚假的亲近或每句开玩笑。'
        '画面表达意思而非逐字配图，镜头和留白服务观点与情绪；电影感按需来自构图、光线、色彩和节奏。'
        '提交前在本次创作内核对信息是否保留、表达是否冗余；导演说明不进入TTS朗读正文，不输出检查过程。'
    ),
    'visual': (
        '画面与剪辑：依据冻结方案的意思、必要事实和动作选择素材，不用关键词相近但无关的镜头凑数。'
        '合理示意、实拍与生成画面可互补；示意不伪装事实证据，操作教学的必要步骤和关键动作不能省略。'
        '按观点、动作和情绪安排镜头，允许有意义的停留、快切与留白；避免无用途固定节拍切镜、机械推拉和转场堆叠。'
        '电影感按需落实到构图、光线、色彩与节奏，不要求每片电影化。'
        '在符合画意的候选中优先清晰、准确对焦、压缩少的源片；裁切预留源分辨率，不把低清放大或锐化光晕当清晰度提升。'
        '仅在当前获准范围内选择和编辑；不为自然度改写冻结口播、音轨、声音参数或字幕时码，必要内容改动走既有范围确认。'
    ),
    'review': (
        '审阅：结合本次导演意图和实际收到的文字、画面或声音，检查是否自然、可信、易理解及有无事实漂移。'
        '套话、机械节奏只是线索；命中某词或笼统说像AI不能作为失败依据，不打去AI分数。'
        'findings须指明具体句段或时间、实际证据和受损的事实、理解或明确要求；已确认影响用户接受的具体缺陷不得藏入建议。'
        '可选表达或审美改善放suggestions，未见未听及观察范围放limitations，不强迫统一文风。'
        '只审已有证据，不将稿件当作听过配音、不将抽帧当作看完连续动作，不声称Creator已接受。'
    ),
}


def _digest(version, rules):
    return hashlib.sha256(json.dumps({'version': version, 'rules': rules},
        sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def snapshot() -> dict:
    rules = deepcopy(RULES)
    return {'version': VERSION, 'digest': _digest(VERSION, rules), 'rules': rules}


def validate(policy) -> dict:
    # Validate the stored finite snapshot, not equality with today's defaults.
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
    return deepcopy(policy)


def instructions(policy, role: ExpressionRole) -> str:
    if role not in ('write', 'visual', 'review'):
        raise ValueError('Unknown expression role')
    saved = validate(policy)
    return '\n' + saved['rules']['core'] + '\n' + saved['rules'][role]
