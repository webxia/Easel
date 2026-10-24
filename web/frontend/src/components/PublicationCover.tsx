import {useRef,useState} from 'react';
import {fetchOutputs,mediaUrl,type OutputFile} from '../lib/api';
import {artifactURL,productionRequest} from '../lib/productionApi';
import {publicationCall,publicationCoverURL,type Publication,type PublicationCover as Cover} from '../lib/publicationApi';

type Props={draft:Publication;cover?:Cover|null;disabled:boolean;onChange:(cover:Cover|null)=>void;run:(action:()=>Promise<void>)=>Promise<void>};
export default function PublicationCover({draft,cover,disabled,onChange,run}:Props){
 const [mode,setMode]=useState<'images'|'frame'|null>(null),[images,setImages]=useState<OutputFile[]>([]);
 const [candidate,setCandidate]=useState<Cover|null>(null),[at,setAt]=useState(0);
 const input=useRef<HTMLInputElement>(null),video=useRef<HTMLVideoElement>(null);
 const upload=(file:File)=>run(async()=>{
  const body=new FormData();body.append('revision',String(draft.revision));body.append('file',file);
  setCandidate(await productionRequest<Cover>(`publications/${draft.id}/covers/upload`,{method:'POST',body}));
 });
 const chooseImages=()=>run(async()=>{
  const files:OutputFile[]=[];
  const walk=(n:OutputFile)=>{if(n.type==='file'){if(n.kind==='image')files.push(n);}else n.children?.forEach(walk);};
  (await fetchOutputs()).forEach(walk);files.sort((a,b)=>(b.mtime||0)-(a.mtime||0));setImages(files);setMode('images');
 });
 return <div className="publication-cover">
  <span className="field-label">投稿封面</span>
  {cover?<img className="publication-cover-image" src={publicationCoverURL(draft.id,cover.digest)} alt="已选择的投稿封面"/>:<p className="page-subtitle">未选择自定义封面，将由B站默认处理。</p>}
  {draft.state==='draft'&&<>
   <p className="page-subtitle">上传图片、选择已有图片素材，或从本片截取画面。先预览选用，再保存草稿。</p>
   <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden aria-label="上传封面图片" disabled={disabled} onChange={e=>{const f=e.target.files?.[0];e.target.value='';if(f)void upload(f);}}/>
   <div className="publish-actions"><button type="button" className="btn btn-sm" disabled={disabled} onClick={()=>input.current?.click()}>上传图片</button><button type="button" className="btn btn-sm" disabled={disabled} onClick={()=>void chooseImages()}>选择已有图片</button><button type="button" className="btn btn-sm" disabled={disabled} onClick={()=>setMode(mode==='frame'?null:'frame')}>从本片截图</button>{cover&&<button type="button" className="btn btn-ghost btn-sm" disabled={disabled} onClick={()=>{setCandidate(null);onChange(null);}}>使用平台默认</button>}</div>
   {mode==='images'&&<div className="media-grid" aria-label="选择封面素材">{!images.length&&<p className="page-subtitle">暂无图片素材，可上传图片或从本片截图。</p>}{images.slice(0,40).map(image=><button type="button" className="media-cell" key={image.path} disabled={disabled} aria-label={`预览 ${image.name}`} onClick={()=>void run(async()=>setCandidate(await publicationCall<Cover>(`/${draft.id}/covers`,{revision:draft.revision,library_path:image.path})))}><img src={mediaUrl(image.path)} alt={image.name} loading="lazy"/></button>)}</div>}
   {mode==='frame'&&<div className="publication-frame-picker"><video ref={video} controls preload="metadata" src={artifactURL(draft.output_id)} className="publication-video" onSeeked={e=>setAt(e.currentTarget.currentTime)}/><p className="page-subtitle">拖动进度条选择画面；当前选择约 {at.toFixed(2)} 秒。</p><button type="button" className="btn btn-sm" disabled={disabled} onClick={()=>void run(async()=>{const time=video.current?.currentTime??at;video.current?.pause();setAt(time);setCandidate(await publicationCall<Cover>(`/${draft.id}/covers`,{revision:draft.revision,at:time}));})}>截取当前画面并预览</button></div>}
   {candidate&&<div className="card publication-cover-candidate"><h3>封面预览</h3><img className="publication-cover-image" src={publicationCoverURL(draft.id,candidate.digest)} alt="待选用封面预览"/><p className="page-subtitle">{candidate.width} × {candidate.height}，保持原比例。此图尚未保存到草稿。</p><div className="publish-actions"><button type="button" className="btn btn-primary btn-sm" disabled={disabled} onClick={()=>{onChange(candidate);setCandidate(null);setMode(null);}}>使用这张封面</button><button type="button" className="btn btn-ghost btn-sm" disabled={disabled} onClick={()=>setCandidate(null)}>放弃这张</button></div></div>}
  </>}
 </div>;
}
