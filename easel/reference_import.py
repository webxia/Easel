"""Explicit reference-only HTTPS import with bounded, pinned public-IP transport."""
from __future__ import annotations
import hashlib
import http.client
import ipaddress
import json
import socket
import ssl
import uuid
from urllib.parse import urlsplit, urljoin

from .conversation import ConversationService
from .production.service import digest, encode, fail, now

MAX_BYTES=100*1024*1024


def public_target(url):
    parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.port not in (None,443) or parts.fragment:
        fail('invalid_reference_url','请提供无登录信息的公开 HTTPS 视频直链')
    addresses={value[4][0] for value in socket.getaddrinfo(parts.hostname,443,type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        fail('reference_source_blocked','参考地址不可指向本机、内网或保留网络',403)
    return parts,sorted(addresses)[0]


def download_reference(url,destination):
    for _ in range(4):
        parts,ip=public_target(url)
        connection=http.client.HTTPSConnection(parts.hostname,timeout=20,context=ssl.create_default_context())
        # Pin the vetted IP while retaining the original TLS hostname and Host header.
        connection._create_connection=lambda address,timeout,source_address=None:socket.create_connection((ip,443),timeout,source_address)
        try:
            path=parts.path or '/'
            if parts.query:path+='?'+parts.query
            connection.request('GET',path,headers={'Accept':'video/*','User-Agent':'Easel-reference-import/2'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:fail('reference_unavailable','参考跳转缺少目标')
                url=urljoin(url,location);continue
            if response.status!=200:fail('reference_unavailable','未能访问参考视频，请上传本地文件')
            media=response.getheader('Content-Type','').split(';')[0].lower()
            if not media.startswith('video/'):fail('reference_format_unavailable','链接不是可直接读取的视频；请提供视频直链或上传文件')
            length=response.getheader('Content-Length')
            if length and (not length.isdigit() or int(length)>MAX_BYTES):fail('reference_too_large','参考视频超过100MB，请上传本地素材')
            total=0
            with destination.open('xb') as output:
                while data:=response.read(1024*1024):
                    total+=len(data)
                    if total>MAX_BYTES:fail('reference_too_large','参考视频超过100MB')
                    output.write(data)
            if not total:fail('reference_unavailable','参考视频为空')
            # Real media inspection rather than trusting extension/content type.
            from .production.media import probe_media
            metadata=probe_media(destination)
            if not metadata.get('streams') or not any(s.get('codec_type')=='video' for s in metadata['streams']):fail('reference_format_unavailable','未取得有效视频画面')
            return {'url':url,'bytes':total,'digest':hashlib.sha256(destination.read_bytes()).hexdigest()}
        finally:connection.close()
    fail('reference_unavailable','参考视频跳转过多')


def import_reference(service,session,segment_id,url,command_id,expected_revision,*,downloader=download_reference):
    c=ConversationService(service);request_hash=digest([session,segment_id,url,expected_revision])
    # Persist before any network side effect. Unknown/failed fetch is never blindly repeated.
    with service.store.transaction() as conn:
        segment=c.segment(conn,session,segment_id)
        old=conn.execute('SELECT * FROM conversation_imports WHERE id=?',(command_id,)).fetchone()
        if old:
            if old['request_hash']!=request_hash:fail('command_conflict','同一导入标识不能用于不同参考',409)
            if old['state']=='succeeded':return json.loads(old['result_json'])
            fail('reference_import_pending','原参考导入待核实或失败；请检查已有结果，不自动重发',409)
        if not segment['work_id']:fail('work_not_bound','请先确认参考作品草稿',409)
        work=service.store.get_work(segment['work_id'],connection=conn)
        if work['revision']!=expected_revision:fail('stale_revision','作品输入已变化',409)
        service._ensure_idle(conn,work)
        conn.execute('INSERT INTO conversation_imports VALUES (?,?,?,?,NULL,?)',(command_id,segment_id,request_hash,'sending',now()))
    scope=hashlib.sha256(session.encode()).hexdigest()[:20]
    relative=f'_inbox/{scope}/{uuid.uuid4().hex}/reference.mp4';path=service.outputs/relative;path.parent.mkdir(parents=True,exist_ok=False)
    try:
        metadata=downloader(url,path)
        attachment={'path':relative,'id':hashlib.sha256((scope+'\0'+relative).encode()).hexdigest()[:24],'name':'reference.mp4'}
        with service.store.transaction() as conn:
            # Input registration uses its originally observed Work revision; no conflict retry.
            c.segment(conn,session,segment_id)
            result=service.command('input',{'session_id':session,'attachment':attachment,'usage':'reference','rights':{'status':'UNKNOWN'}},command_id=command_id+'_input',work_id=segment['work_id'],expected_revision=expected_revision,_connection=conn)
            value=conn.execute('SELECT metadata_json FROM work_inputs WHERE id=?',(result['input_id'],)).fetchone()
            source=json.loads(value[0]);source['reference_import']={'url':metadata['url'],'digest':metadata['digest'],'use':'style_reference_only'}
            conn.execute('UPDATE work_inputs SET metadata_json=? WHERE id=?',(encode(source),result['input_id']))
            conn.execute("UPDATE conversation_imports SET state='succeeded',result_json=? WHERE id=?",(encode(result),command_id))
        return result
    except BaseException:
        with service.store.transaction() as conn:conn.execute("UPDATE conversation_imports SET state='needs_review' WHERE id=?",(command_id,))
        raise
