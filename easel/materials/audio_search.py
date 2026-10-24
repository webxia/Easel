"""Local bilingual audio metadata ranking; never claims to hear the recording."""
import re

# Phrase vocabulary, deliberately limited to recorded objects/actions. Unknown
# words retain lexical matching rather than being guessed by a model.
CONCEPTS = {
    'cup': (r'杯', r'\b(?:cups?|mugs?|glass(?:es)?)\b'),
    'door': (r'门', r'\bdoors?\b'),
    'keyboard': (r'键盘|打字', r'\bkeyboard\b|\btyping\b'),
    'air': (r'空调', r'\bair conditioner\b'),
    'ambience': (r'环境声|环境音|背景声', r'\bambien(?:ce|t)\b|\broom ?tone\b'),
    'page': (r'翻页|翻书|书页|书本|报纸|杂志', r'\b(?:pages?|books?|newspapers?|magazines?)\b'),
    'paper': (r'纸张|纸页|纸', r'\bpaper\b'),
    'pen': (r'钢笔|铅笔|圆珠笔|笔尖', r'\b(?:pens?|pencils?)\b'),
    'place': (r'放下|轻放|放杯|放在|放到', r'\bset(?:ting)? down\b|\bput(?:ting)? down\b|\bplac(?:e|ed|ing)\b'),
    'open': (r'开门|打开|开启', r'\bopen(?:s|ed|ing)?\b'),
    'close': (r'关门|关闭|关上', r'\bclos(?:e|es|ed|ing)\b|\bshut\b'),
    'type': (r'打字|连续敲|连续按', r'\btyp(?:e|es|ed|ing)\b'),
    'single': (r'单键|单次按', r'\bsingle (?:hit|key)\b|\bspace bar\b'),
    'break': (r'破碎|打碎|碎玻璃', r'\bbreak(?:s|ing)?\b|\bbroken\b|\bshatter\w*\b'),
    'turn_page': (r'翻页|翻书|翻阅|书页翻动|翻动书页',
                  r'\b(?:turn(?:s|ed|ing)?|flip(?:s|ped|ping)?) (?:to )?(?:a )?pages?\b',
                  r'\bpages? (?:turn(?:s|ed|ing)?|flip(?:s|ped|ping)?)\b',
                  r'\b(?:thumb|flip)(?:s|ed|ped|ing)? through\b'),
    'rustle': (r'沙沙|窸窣|窸窸窣窣|纸张摩擦', r'\brustl(?:e|es|ed|ing)\b'),
    'crumple': (r'揉纸|揉皱|揉成团', r'\bcrum(?:bl|pl)(?:e|es|ed|ing)\b'),
    'tear': (r'撕纸|撕开|撕裂|撕碎', r'\btear(?:s|ing)?\b|\btorn\b|\brip(?:s|ped|ping)?\b'),
    'write': (r'写字|书写|写在纸上', r'\bwrit(?:e|es|ing|ten)\b|\bwrote\b'),
}
OBJECTS = {'cup', 'door', 'keyboard', 'air', 'ambience', 'page', 'paper', 'pen'}
ACTIONS = {'place', 'open', 'close', 'type', 'single', 'break',
           'turn_page', 'rustle', 'crumple', 'tear', 'write'}

def concepts(text):
    text = re.sub(r'[_-]', ' ', text.casefold())
    return {key for key, patterns in CONCEPTS.items() if any(re.search(p, text) for p in patterns)}


def audio_action_conflict(query, caption):
    """Only source-declared conflicting actions; an unknown term is not a veto."""
    requested, actual = concepts(query), concepts(caption)
    opposites = ({'open', 'close'}, {'place', 'break'}, {'type', 'single'},
                 {'turn_page', 'close'}, {'turn_page', 'tear'},
                 {'rustle', 'tear'}, {'write', 'tear'})
    for pair in opposites:
        wanted = requested & pair
        if len(wanted) == 1 and actual & pair and not wanted & actual:
            return True
    if 'break' in requested and re.search(r"does(?:n['’]t| not) break|not broken|不破|未破", caption.casefold()):
        return True
    # Erasing is source evidence of a different action, not an unknown verb.
    return bool('write' in requested and 'write' not in actual and
                re.search(r'\beras(?:e|es|ed|ing|er)\b|擦除|橡皮', caption.casefold()))

def score_audio(query, caption, metadata):
    """Return None to use generic matching; zero explicitly rejects a mismatch."""
    requested = concepts(query)
    if not requested:
        return None
    # Prefer source caption for action identity: broad imported tags must not
    # turn a single keystroke into continuous typing.
    actual = concepts(caption or '')
    actual |= concepts(metadata) & OBJECTS
    if not actual:
        actual = concepts(metadata)
    if re.search(r'\b(?:bottles?|fragments?|debris)\b', caption.casefold()) and not re.search(r'\b(?:cups?|mugs?)\b', caption.casefold()):
        actual.discard('cup')
    objects, actions = requested & OBJECTS, requested & ACTIONS
    if objects and not objects.intersection(actual):
        return 0.0
    if actions and not actions.intersection(actual):
        return 0.0
    if 'break' in actions and re.search(r"does(?:n['’]t| not) break|not broken|不破|未破", caption.casefold()):
        return 0.0
    if 'type' in actions and 'single' in actual and 'type' not in actual:
        return 0.0
    # Exact action and object dominate generic shared words.
    base = 3 * len(objects & actual) + 5 * len(actions & actual)
    # A specific object name beats a multi-object recording; contextual words
    # improve ordering without claiming unrecorded acoustic properties.
    if 'cup' in objects and re.search(r'\b(?:box|crate|bottles?)\b', caption.casefold()):
        base -= 2
    context_words = {'卧室': 'bedroom', '房间': 'room', '木': 'wood', '笔记本': 'laptop',
                     '杂志': 'magazine', '报纸': 'newspaper', '铅笔': 'pencil'}
    base += sum(1 for cn, en in context_words.items() if cn in query and en in caption.casefold())
    words = set(re.findall(r'[a-z]+', query.casefold()))
    terms = set(re.findall(r'[a-z]+', caption.casefold()))
    return float(base) + len(words & terms) / max(1, len(words))



def audio_content_kind(title, categories=''):
    """Classify file-level declarations, never the music mentioned by a talk.

    Source role and mood search keywords are not evidence about audio content.
    This is metadata evidence only, not a claim that the recording was heard.
    """
    text=re.sub(r'[_|;-]', ' ', (title+' '+categories).casefold())
    if re.search(r'\b(?:spoken[ -]?word|speeches|speech|lectures?|interviews?|podcasts?|'
                 r'oral history|introductory audios?|inleiding|gesproken|audiobooks?)\b|'
                 r'导赏|导聆|访谈|演讲|讲座|有声读物|口述',text):
        return 'speech'
    if re.search(r'\b(?:music|instrumentals?|piano|guitar|ambient|symphon(?:y|ies)|'
                 r'sonatas?|concertos?|preludes?|etudes?|nocturnes?|orchestra|jazz|'
                 r'soundtracks?|compositions?)\b|纯音乐|器乐|钢琴曲|背景音乐',text):
        return 'music'
    return 'unclassified'


MUSIC_CONTENT_ISSUES=frozenset({'spoken_audio_not_music','music_content_unclassified'})


def music_candidate_issue(semantic, source):
    """One purpose-fit rule shared by discovery, library reuse and selection."""
    from urllib.parse import unquote, urlsplit
    attrs=semantic.get('attributes') or {}
    filename=unquote(urlsplit(source.get('source_page') or '').path).rsplit('/',1)[-1]
    title=(semantic.get('caption') or '')+' '+filename.removeprefix('File:')
    kind=audio_content_kind(title,attrs.get('source_categories',''))
    if kind=='speech' or attrs.get('audio_content_kind')=='speech':
        return 'spoken_audio_not_music'
    if (source.get('provider')=='wikimedia_bgm' and kind!='music'
            and attrs.get('audio_content_kind')!='music'):
        return 'music_content_unclassified'
    return None
