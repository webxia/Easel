"""Local media execution, independent of the host and Easel production database."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .core import CreativeError, atomic, digest, lock, number, read, require, sha, token


def run(args, cwd=None, timeout=1800):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise CreativeError('media_command_failed', result.stderr[-4000:])
    return result.stdout


def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],timeout=30))


def duration(asset):
    return float(asset['media'].get('format',{}).get('duration',0))


def keys(value, allowed):
    require(isinstance(value,dict) and not (set(value)-set(allowed)), 'unknown_field',
            f'Allowed fields: {", ".join(allowed)}')


def validate_plan(project, plan):
    keys(plan, ['width','height','fps','scenes','tracks','captions','audio_mode'])
    for key in ['width','height']:
        require(type(plan.get(key)) is int and 64<=plan[key]<=3840 and plan[key]%2==0,
                'invalid_dimensions','Even dimensions between 64 and 3840 required')
    require(plan.get('fps') in [24,25,30,60], 'invalid_fps', 'Supported fps: 24/25/30/60')
    mode=plan.get('audio_mode','voice')
    require(mode in ['silent','voice','music','mixed'], 'invalid_audio_mode','Unknown sound mode')
    scenes=plan.get('scenes',[])
    require(isinstance(scenes,list) and 1<=len(scenes)<=128,'invalid_scenes','1–128 scenes required')
    total=0
    for group in ['scenes','tracks','captions']:
        ids=[token(x['id']) for x in plan.get(group,[])]
        require(len(ids)==len(set(ids)), 'duplicate_id', f'Duplicate {group} IDs')
    for scene in scenes:
        keys(scene,['id','asset','duration','source_start','fit','frame','motion','fade_in','fade_out'])
        asset,_=project.asset(scene['asset'])
        require(asset['kind'] in ['image','video'],'wrong_media','Scene needs image/video')
        seconds=number(scene['duration'],1/plan['fps']); total+=seconds
        start=number(scene.get('source_start',0))
        if asset['kind']=='video':
            require(start+seconds<=duration(asset)+1/plan['fps'],'source_bounds',f'Scene {scene["id"]} exceeds source')
        require(scene.get('fit','contain') in ['contain','cover'],'invalid_fit','Use contain or cover')
        require(scene.get('motion','none') in ['none','push_in','pull_out'],'invalid_motion','Unsupported motion')
        frame=scene.get('frame',[0,0,1,1])
        require(isinstance(frame,list) and len(frame)==4,'invalid_frame','Frame is [x,y,width,height]')
        for v in frame: number(v,0,1)
        require(frame[2]>0 and frame[3]>0 and frame[0]+frame[2]<=1 and frame[1]+frame[3]<=1,
                'invalid_frame','Frame exceeds canvas')
        require(number(scene.get('fade_in',0))+number(scene.get('fade_out',0))<=seconds,
                'invalid_fade','Fades exceed scene duration')
    number(total,1,900)
    roles=set()
    for track in plan.get('tracks',[]):
        keys(track,['id','asset','role','start','source_start','duration','gain','fade_in','fade_out'])
        asset,_=project.asset(track['asset'])
        require(any(s['codec_type']=='audio' for s in asset['media']['streams']), 'wrong_media','Track needs audio')
        require(track['role'] in ['voice','music','sfx','source'],'invalid_role','Unknown track role')
        roles.add(track['role'])
        start=number(track['start']); seconds=number(track['duration'],0.001); source=number(track.get('source_start',0))
        require(start+seconds<=total+1/plan['fps'],'track_bounds','Track exceeds timeline')
        require(source+seconds<=duration(asset)+0.03,'source_bounds','Track exceeds source')
        number(track.get('gain',1),0,4)
        require(number(track.get('fade_in',0))+number(track.get('fade_out',0))<=seconds,'invalid_fade','Audio fades exceed track')
    voice=bool(roles & {'voice','source'}); music='music' in roles
    require((mode!='silent' or not roles) and (mode!='voice' or (voice and not music))
            and (mode!='music' or (music and not voice)) and (mode!='mixed' or (voice and music)),
            'audio_mode_mismatch','Tracks do not match the requested sound mode')
    for caption in plan.get('captions',[]):
        keys(caption,['id','text','start','end','font','size','y','color','background','role'])
        require(isinstance(caption['text'],str) and 0<len(caption['text'])<=1000,'invalid_caption','Caption text required, up to 1000 characters')
        start=number(caption['start']); end=number(caption['end'])
        require(start<end<=total+1/plan['fps'],'caption_bounds','Caption outside timeline')
        font,_=project.asset(caption['font'])
        require(font['kind']=='font','wrong_media','Caption requires font asset')
        number(caption.get('size',40),8,200); number(caption.get('y',0.84),0,1)
        require(caption.get('role','narration') in ['narration','overlay'],'invalid_role','Unknown caption role')
    return total


def caption_png(project, caption, width, height, path):
    from PIL import Image, ImageDraw, ImageFont, ImageColor
    _,fontpath=project.asset(caption['font'])
    font=ImageFont.truetype(str(fontpath),int(caption.get('size',40)))
    image=Image.new('RGBA',(width,height),(0,0,0,0)); draw=ImageDraw.Draw(image)
    lines=[]; line=''; max_width=width*0.9
    for char in caption['text']:
        if char=='\n' or (line and draw.textlength(line+char,font=font)>max_width):
            lines.append(line); line='' if char=='\n' else char
        else: line+=char
    if line: lines.append(line)
    text='\n'.join(lines); box=draw.multiline_textbbox((0,0),text,font=font,spacing=6)
    tw,th=box[2]-box[0],box[3]-box[1]; y=round(height*caption.get('y',0.84))
    require(th+16<=height and y+th+16<=height,'caption_overflow','Caption exceeds frame; adjust size/y/text')
    x=(width-tw)//2
    if caption.get('background',True): draw.rounded_rectangle((x-12,y-8,x+tw+12,y+th+8),radius=6,fill=(0,0,0,170))
    draw.multiline_text((x-box[0],y-box[1]),text,font=font,fill=ImageColor.getrgb(caption.get('color','#ffffff')),spacing=6,align='center')
    image.save(path)


def start_render(project, revision=None):
    data=project.revision(revision); plan=data['plan']
    require(data['confirmed']==digest({'script':data['script'],'plan':plan,'context':data['context']}),
            'not_confirmed','Confirm the exact plan/context before rendering')
    validate_plan(project,plan)
    job=f'r{data["revision"]}-{digest(plan)[:16]}'
    folder=project.root/'renders'/job; folder.mkdir(parents=True,exist_ok=True)
    with lock(folder/'submit.lock'):
        if (folder/'receipt.json').exists():
            state=render_status(project,job)
            if state['state']=='succeeded':
                require(sha(project.path(state['video']))==state['sha256'],'output_changed','Rendered output changed')
                return state
            if state['state'] in ['queued','running']: return state
        receipt={'job_id':job,'revision':data['revision'],'state':'queued','created_at':time.time()}
        atomic(folder/'receipt.json',receipt)
        env=os.environ.copy()
        env['PYTHONPATH']=str(Path(__file__).resolve().parent.parent)
        with (folder/'worker.log').open('a') as log:
            subprocess.Popen([sys.executable,'-m','easel_creative.cli','--project',str(project.root),
                              '_render',job],stdout=log,stderr=log,env=env,start_new_session=(os.name!='nt'))
        return receipt


def render_status(project,job):
    folder=project.root/'renders'/token(job); receipt=read(folder/'receipt.json')
    if receipt['state']=='running' or (receipt['state']=='queued' and time.time()-receipt['created_at']>30):
        try:
            with lock(folder/'worker.lock',False):
                receipt=read(folder/'receipt.json')
                if receipt['state'] in ['queued','running']:
                    receipt.update(state='interrupted',error='Worker exited; local-only render may be restarted')
                    atomic(folder/'receipt.json',receipt)
        except (BlockingIOError,OSError): pass
    return receipt


def render_worker(project,job):
    folder=project.root/'renders'/token(job)
    with lock(folder/'worker.lock'):
        receipt=read(folder/'receipt.json')
        if receipt['state']=='succeeded': return receipt
        receipt['state']='running'; atomic(folder/'receipt.json',receipt)
        try:
            data=project.revision(receipt['revision']); plan=data['plan']
            total=validate_plan(project,plan); w,h,fps=plan['width'],plan['height'],plan['fps']
            cache=project.root/'cache'; cache.mkdir(exist_ok=True)
            clips=[]
            for index,scene in enumerate(plan['scenes']):
                asset,src=project.asset(scene['asset'])
                key=digest({'scene':scene,'sha':asset['sha256'],'w':w,'h':h,'fps':fps,'renderer':1})
                target=cache/f'{key}.mp4'
                with lock(cache/f'{key}.lock'):
                    if not target.exists():
                        tmp=cache/f'{key}.partial.mp4'
                        cmd=['ffmpeg','-nostdin','-v','error','-y','-threads','2']
                        if asset['kind']=='image': cmd+=['-loop','1','-framerate',str(fps)]
                        else: cmd+=['-ss',str(scene.get('source_start',0))]
                        cmd+=['-i',str(src)]
                        x,y,fw,fh=scene.get('frame',[0,0,1,1]); fw=max(2,int(w*fw)//2*2); fh=max(2,int(h*fh)//2*2)
                        fit=scene.get('fit','contain')
                        vf=f'scale={fw}:{fh}:force_original_aspect_ratio={"decrease" if fit=="contain" else "increase"}'
                        vf+=f',pad={fw}:{fh}:(ow-iw)/2:(oh-ih)/2:black' if fit=='contain' else f',crop={fw}:{fh}'
                        frames=round(scene['duration']*fps)
                        motion=scene.get('motion','none')
                        if motion!='none':
                            z=f'1+0.08*on/{max(frames-1,1)}' if motion=='push_in' else f'1.08-0.08*on/{max(frames-1,1)}'
                            # A frame-at-a-time zoom preserves the original clip duration.
                            vf+=f",zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={fw}x{fh}:fps={fps}"
                        vf+=f',pad={w}:{h}:{int(x*w)}:{int(y*h)}:black,setsar=1,fps={fps}'
                        if scene.get('fade_in',0): vf+=f',fade=t=in:st=0:d={scene["fade_in"]}'
                        if scene.get('fade_out',0): vf+=f',fade=t=out:st={scene["duration"]-scene["fade_out"]}:d={scene["fade_out"]}'
                        cmd+=['-vf',vf,'-frames:v',str(frames),'-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',str(tmp)]
                        run(cmd); os.replace(tmp,target)
                clips.append(target)
                receipt['progress']={'scenes_done':index+1,'scenes_total':len(plan['scenes'])}; atomic(folder/'receipt.json',receipt)
            # Only generated hexadecimal file names enter the concat grammar.
            listing=folder/'concat.txt'; listing.write_text(''.join(f"file '{p.as_posix()}'\n" for p in clips))
            montage=folder/'montage.mp4'
            run(['ffmpeg','-nostdin','-v','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(montage)])
            cmd=['ffmpeg','-nostdin','-v','error','-y','-threads','2','-i',str(montage)]
            filters=[]; video='0:v'; input_index=1
            for i,caption in enumerate(plan.get('captions',[])):
                png=folder/f'caption-{i}.png'; caption_png(project,caption,w,h,png)
                cmd+=['-loop','1','-framerate',str(fps),'-i',str(png)]
                out=f'v{i}'
                filters.append(f"[{video}][{input_index}:v]overlay=enable='gte(t,{caption['start']})*lt(t,{caption['end']})'[{out}]")
                video=out; input_index+=1
            audio=[]
            for i,track in enumerate(plan.get('tracks',[])):
                _,src=project.asset(track['asset']); cmd+=['-i',str(src)]
                chain=f'[{input_index}:a]atrim=start={track.get("source_start",0)}:duration={track["duration"]},asetpts=PTS-STARTPTS,volume={track.get("gain",1)}'
                if track.get('fade_in',0): chain+=f',afade=t=in:d={track["fade_in"]}'
                if track.get('fade_out',0): chain+=f',afade=t=out:st={track["duration"]-track["fade_out"]}:d={track["fade_out"]}'
                chain+=f',adelay={round(track["start"]*1000)}:all=1[a{i}]'
                filters.append(chain); audio.append(f'[a{i}]'); input_index+=1
            if audio: filters.append(''.join(audio)+f'amix=inputs={len(audio)}:normalize=0,apad,atrim=duration={total}[audio]')
            if filters: cmd+=['-filter_complex_threads','1','-filter_complex',';'.join(filters)]
            cmd+=['-map',f'[{video}]' if video!='0:v' else '0:v']
            if audio: cmd+=['-map','[audio]','-c:a','aac','-b:a','192k']
            else: cmd+=['-an']
            final=folder/'final.mp4'; tmp=folder/'final.partial.mp4'
            cmd+=['-t',str(total),'-r',str(fps),'-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)]
            run(cmd); run(['ffmpeg','-nostdin','-v','error','-i',str(tmp),'-f','null','-'])
            info=probe(tmp)
            require(abs(float(info['format']['duration'])-total)<=max(0.15,len(clips)/fps), 'duration_mismatch','Output duration differs from plan')
            os.replace(tmp,final)
            receipt.update(state='succeeded',video=str(final.relative_to(project.root)),sha256=sha(final),duration=float(info['format']['duration']),
                           technical_checks={'decoded':True,'duration':True},creative_review='NOT_TESTED',
                           scene_cache=[p.name for p in clips],finished_at=time.time())
        except Exception as exc:
            receipt.update(state='failed',error=str(exc),error_code=getattr(exc,'code','render_failed'))
        atomic(folder/'receipt.json',receipt)
        return receipt


def inspect(project,asset_id,seconds=0):
    asset,path=project.asset(asset_id)
    if asset['kind'] not in ['video','image']: return {'asset':asset,'observation':'No visual stream'}
    number(seconds)
    target=project.root/'observations'/f'{asset_id}-{seconds}.png'; target.parent.mkdir(exist_ok=True)
    run(['ffmpeg','-nostdin','-v','error','-y','-ss',str(seconds),'-i',str(path),'-frames:v','1',str(target)])
    require(target.exists(),'observation_failed','No frame at requested time')
    return {'asset':asset,'frame':str(target),'seconds':seconds}
