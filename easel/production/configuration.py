"""Read service identities without exposing credentials or authorizing calls."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from easel.direct_api import read_settings, api_config, DirectAPIError


def model_configuration(root: Path):
    settings=read_settings(root/'.env')
    try:
        base,model,_=api_config(settings)
    except DirectAPIError:
        return settings,None,None
    # Endpoint identity is hashed; changing endpoint invalidates the recorded configuration.
    version=hashlib.sha256(json.dumps({'base':base,'model':model,
        'capabilities':sorted({part.strip() for part in settings.get('EASEL_PRODUCTION_MODEL_CAPABILITIES','image').split(',') if part.strip()}),
        'video_dialect':settings.get('EASEL_PRODUCTION_VIDEO_DIALECT','').strip(),
        'quality_chunk_seconds':settings.get('EASEL_PRODUCTION_QUALITY_CHUNK_SECONDS','30'),
        'model_timeout_seconds':settings.get('EASEL_PRODUCTION_MODEL_TIMEOUT_SECONDS','900')},sort_keys=True).encode()).hexdigest()
    service={'provider':'direct-api','model':model,'mode':'structured'}
    return settings,service,version


def capabilities(root: Path):
    settings,model,_=model_configuration(root)
    services=[]
    if model:services.append({**model,'label':'创作模型 · '+model['model'],'available':True})
    from .supply_tasks import supply_capabilities
    services.extend(supply_capabilities(settings))
    # Unsplash V1 is discovery-only: the API requires hotlinked previews,
    # photographer credit and a tracked download on explicit selection.
    for provider, env_key, kinds, supports_production in (
        ('pexels', 'PEXELS_API_KEY', ('image', 'video'), True),
        ('pixabay', 'PIXABAY_API_KEY', ('image', 'video'), True),
        ('unsplash', 'UNSPLASH_ACCESS_KEY', ('image',), False),
    ):
        configured = bool(settings.get(env_key, '').strip())
        services.append({'provider': provider, 'model': 'stock',
            'mode': 'search' if supports_production else 'discovery',
            'label': ('素材检索 · ' if supports_production else '素材预览 · ') + provider,
            'media_types': list(kinds), 'configured': configured, 'available': configured,
            'supports_auto_supply': supports_production,
            'reason': 'explicit_selection_required' if configured and not supports_production else
                ('capability_unavailable' if not configured else None)})
    wikimedia_enabled = settings.get('EASEL_WIKIMEDIA_AUDIO_ENABLED', '0').strip() == '1'
    for provider, role in (('wikimedia_bgm', 'music'), ('wikimedia_sfx', 'sfx')):
        services.append({'provider': provider, 'model': 'stock', 'mode': 'search',
            'label': 'Wikimedia Commons · ' + ('背景音乐' if role == 'music' else '音效'),
            'media_types': ['audio'], 'audio_roles': [role],
            'configured': wikimedia_enabled, 'available': wikimedia_enabled,
            'supports_auto_supply': True,
            'reason': None if wikimedia_enabled else 'capability_unavailable'})
    from .public_facts import public_fact_capabilities
    services.extend(public_fact_capabilities(settings))
    # Use the same pure parser as execution; missing keys/unsupported protocols
    # must not appear usable merely because a voices array was configured.
    from .voice import configured_speech_configs
    from .errors import ProductionError
    try:
        for config in configured_speech_configs(settings):
            ready=any(option.available for option in config.voices)
            services.append({'provider':config.provider,'model':config.model,'mode':config.mode,
                'label':'配音 · '+config.model,'available':ready,
                'reason':None if ready else 'voice_unavailable'})
    except ProductionError:
        services.append({'provider':'voice-configuration','model':'invalid','mode':'speech',
            'label':'声音配置需要修正','available':False,'reason':'voice_configuration_invalid'})
    from .providers.stock import ReviewedPublicSources
    raw=settings.get('EASEL_REVIEWED_PUBLIC_SOURCES_JSON','').strip()
    ready=False; media=[]; reason='capability_unavailable'
    if raw:
        try:
            if not raw.startswith('{'):
                path=Path(raw)
                if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)) or path.stat().st_size>256*1024:
                    raise ValueError('Invalid source configuration')
                raw=path.read_text(encoding='utf-8')
            if len(raw.encode('utf-8'))>256*1024:raise ValueError('Source configuration too large')
            provider=ReviewedPublicSources.from_json(raw)
            ready=True; media=sorted(kind.value for kind in provider.media_types); reason=None
        except (ValueError,OSError,TypeError):
            reason='source_configuration_invalid'
    services.append({'provider':'reviewed_public','model':'stock','mode':'search','label':'已审查公开素材',
        'configured':bool(raw),'available':ready,'media_types':media,'supports_auto_supply':True,'reason':reason})
    from .subtitles import configured_fonts
    from .boards import VERSION
    local=[{'renderer':VERSION,'available':bool(configured_fonts(settings)),
            'label':'原生概念/假设图解','counts_toward_generation':False}]
    return {'services':services,'local_visuals':local,'generation_limits':['IMAGE','VIDEO'],
            'voice_counts_toward_generation':False,'model_configured':bool(model)}
