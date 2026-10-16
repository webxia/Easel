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
        'quality_chunk_seconds':settings.get('EASEL_PRODUCTION_QUALITY_CHUNK_SECONDS','30')},sort_keys=True).encode()).hexdigest()
    service={'provider':'direct-api','model':model,'mode':'structured'}
    return settings,service,version


def capabilities(root: Path):
    settings,model,_=model_configuration(root)
    services=[]
    if model:services.append({**model,'label':'创作模型 · '+model['model'],'available':True})
    from .supply_tasks import supply_capabilities
    services.extend(supply_capabilities(settings))
    from .public_facts import public_fact_capabilities
    services.extend(public_fact_capabilities(settings))
    import json
    # Voice services expose only identity; configuration credentials stay private.
    try:
        configs=json.loads(settings.get('EASEL_VOICE_SERVICES_JSON','[]'))
        for config in configs:
            services.append({'provider':config['provider'],'model':config['model'],'mode':'speech',
                'label':'配音 · '+config['model'],'available':bool(config.get('voices'))})
    except (ValueError,KeyError,TypeError):
        pass
    return {'services':services,'generation_limits':['IMAGE','VIDEO'],
            'voice_counts_toward_generation':False,'model_configured':bool(model)}
