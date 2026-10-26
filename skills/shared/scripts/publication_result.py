"""Machine-readable projection of a platform verifier's existing result."""
import json


def emit_verified(platform, matched, account):
    print(json.dumps({'easel_publication':1,'platform':platform,'outcome':'verified',
        'matched':{'platform_content_id':str(matched.platform_content_id),'status':str(matched.status or '')},
        'account_name':str(account.get('display_name') or '')},ensure_ascii=False),flush=True)
