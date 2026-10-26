import BilibiliPartition from './BilibiliPartition';
import {useBilibiliPartitions,partitionLabel} from '../lib/bilibiliPartitions';
import AcceptedPublication from './AcceptedPublication';
import PublicationCover from './PublicationCover';
import {artifactURL,productionRequest} from '../lib/productionApi';
import type {LibraryWork} from '../lib/contentLibrary';
import {openPublishSource,openPublicationDraft,publicationCall,publicationStatus,publicationCoverURL,fileCoverURL,type PublishSource,type Publication,type PublicationCover as Cover} from '../lib/publicationApi';
import { useState, useRef, useEffect, useCallback } from 'react';
import {
  createSchedule, executeSkill, runAgent, streamChat, accountWhoami,
  fetchAccounts, publishNow, publishStatus, submitPublishSms, fetchOutputs, mediaUrl,
} from '../lib/api';
import type { AccountItem, OutputFile } from '../lib/api';
import { loadPublishDraft, savePublishDraft } from '../lib/store';
import { renderMarkdown } from '../lib/sanitize';
import { IconPublish, IconCopy, IconCheck, IconCalendar, IconSkills, IconEdit, IconStop, IconTrash } from './icons';

interface PublishPageProps {
  publicationId?: string;
  source?:PublishSource;
  persona: string;
}

// 平台列表须与后端 LOGIN_RUNNERS 对齐（有登录/发布链路的才列）
const PLATFORMS: { key: string; label: string; titleLimit?: number; bodyLimit: number; hint: string }[] = [
  { key: 'xiaohongshu', label: '小红书', titleLimit: 20, bodyLimit: 1000, hint: '标题≤20，正文≤1000，重情绪+话题标签' },
  { key: 'douyin', label: '抖音', titleLimit: 30, bodyLimit: 55, hint: '文案≤55，前几字是钩子' },
  { key: 'kuaishou', label: '快手', titleLimit: 30, bodyLimit: 1000, hint: '视频或图片(图文)，标题≤30，需附媒体' },
  { key: 'weixin-channels', label: '视频号', bodyLimit: 1000, hint: '需附视频，短描述+话题标签，微信扫码登录' },
  { key: 'zhihu', label: '知乎', bodyLimit: 5000, hint: '长文/回答，讲清逻辑' },
  { key: 'bilibili', label: 'B站', titleLimit: 80, bodyLimit: 2000, hint: '需附视频，标题≤80、简介≤2000，可按名称选择投稿分区' },
  { key: 'wechat-oa', label: '公众号', titleLimit: 64, bodyLimit: 20000, hint: '图文文章，正文用 Markdown，首图作封面，发到草稿箱；需先在账号页「登录公众号后台」扫码' },
];
const LABEL2KEY = Object.fromEntries(PLATFORMS.map((p) => [p.label, p.key]));

// 能一键发布的平台（有后端 publisher）
const PUBLISHABLE = new Set(['xiaohongshu', 'douyin', 'kuaishou', 'weixin-channels', 'zhihu', 'bilibili', 'wechat-oa']);
// 必须附带媒体的平台（无媒体发不了）——公众号需要一张封面图，也计入
const MEDIA_REQUIRED = new Set(['xiaohongshu', 'douyin', 'kuaishou', 'weixin-channels', 'bilibili', 'wechat-oa']);
// 只能发视频的平台（抖音/视频号/B站：图文不走此链路，必须视频）
const VIDEO_ONLY = new Set(['douyin', 'weixin-channels', 'bilibili']);
const VIDEO_RE = /\.(mp4|mov|webm|mkv|avi|m4v|flv|ts)$/i;

function parseSections(text: string): Record<string, string> {
  const parts = text.split(/^\s*={2,}\s*(.+?)\s*={2,}\s*$/m);
  const map: Record<string, string> = {};
  for (let i = 1; i < parts.length; i += 2) map[parts[i].trim()] = (parts[i + 1] || '').trim();
  return map;
}

type PubState = { status: 'publishing' | 'ok' | 'fail'; msg: string };

export default function PublishPage({persona,publicationId,source}:PublishPageProps) {
  const [mode,setMode]=useState<'records'|'edit'>(publicationId?'records':'edit');
  const [current,setCurrent]=useState(source);
  useEffect(()=>{if(publicationId)setMode('records');},[publicationId]);
  useEffect(()=>{if(source){setCurrent(source);setMode('edit');}},[source]);
  return <div className="publication-center"><nav className="publication-modes" aria-label="发布中心导航">
    <button className={`btn btn-sm ${mode==='edit'?'btn-primary':'btn-ghost'}`} onClick={()=>setMode('edit')}>发布内容</button>
    <button className={`btn btn-sm ${mode==='records'?'btn-primary':'btn-ghost'}`} onClick={()=>setMode('records')}>发布记录</button>
    {current&&<button className="btn btn-sm btn-ghost" onClick={()=>{setCurrent(undefined);window.history.replaceState(null,'',window.location.pathname+window.location.search);}}>返回文件草稿</button>}
  </nav>{mode==='records'?<AcceptedPublication selectedId={publicationId}/>:<FilePublishPage key={current?`${current.work_id}:${current.output_id}`:'files'} persona={persona} source={current}/>}</div>;
}

export function FilePublishPage({ persona,source }: {persona:string;source?:PublishSource}) {
  const storageKey=source?`easel_publish_work_${source.work_id}_${source.output_id}`:null;
  const draft0 = (()=>{if(storageKey){try{return JSON.parse(localStorage.getItem(storageKey)||'null')||{title:'',body:'',platforms:['xiaohongshu','douyin'],overrides:{},tags:''};}catch{/* use an empty, independent draft */}return {title:'',body:'',platforms:['xiaohongshu','douyin'],overrides:{},tags:''};}return loadPublishDraft();})();
  const [title, setTitle] = useState(draft0.title);
  const [body, setBody] = useState(draft0.body);
  const [platforms, setPlatforms] = useState<string[]>(draft0.platforms);
  const [overrides, setOverrides] = useState<Record<string, string>>(draft0.overrides);
  const [tags, setTags] = useState(draft0.tags || '');
  const [bilibiliTid,setBilibiliTid]=useState<number>(draft0.bilibiliTid||36);
  const partitions=useBilibiliPartitions(platforms.includes('bilibili'));
  const [editing, setEditing] = useState<string | null>(null);
  const [copied, setCopied] = useState('');
  const [toast, setToast] = useState('');
  const [adapting, setAdapting] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState('');
  const adaptCtl = useRef<AbortController | null>(null);
  // 异步发布轮询的 interval 集合：离开页面统一清掉，否则最长还会继续转 15 分钟
  const pollTimers = useRef<Set<ReturnType<typeof setInterval>>>(new Set());
  const aliveRef = useRef(true);

  // 发布相关
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [mediaFiles, setMediaFiles] = useState<OutputFile[]>([]);
  const [selectedMedia, setSelectedMedia] = useState<string[]>(draft0.media||[]);
  const [works,setWorks]=useState<LibraryWork[]>([]);
  const [records,setRecords]=useState<Record<string,Publication>>({});
  const [savedContents,setSavedContents]=useState<Record<string,string>>({});
  const [mediaError,setMediaError]=useState('');
  const [filter,setFilter]=useState<'all'|'work'|'file'>('all');
  const [query,setQuery]=useState('');
  const [covers,setCovers]=useState<Record<string,Cover|null>>(draft0.covers||{});
  const [fileAccounts,setFileAccounts]=useState<Record<string,string>>({});
  const [coverBusy,setCoverBusy]=useState(false);
  const [confirming,setConfirming]=useState(false);
  const [batch,setBatch]=useState<string[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [pub, setPub] = useState<Record<string, PubState>>({});
  const [publishing, setPublishing] = useState(false);
  // 发布时的短信验证窗口（抖音风控条件触发；没触发就不弹）
  const [pubSms, setPubSms] = useState<{ platform: string; name: string; state: string; message: string } | null>(null);
  const [pubSmsCode, setPubSmsCode] = useState('');
  const [pubSmsBusy, setPubSmsBusy] = useState(false);

  // 草稿持久化：任何改动即写 localStorage，切页/刷新回来都在
  useEffect(() => {
    const value={title,body,platforms,overrides,tags,media:selectedMedia,covers,bilibiliTid};
    if(storageKey)localStorage.setItem(storageKey,JSON.stringify(value));else savePublishDraft(value);
  }, [title, body, platforms, overrides, tags,selectedMedia,covers,bilibiliTid,storageKey]);

  const cleanupPublishActivity = useCallback(() => {
    // 卸载：中止流 + 停掉所有发布状态轮询（否则在后台空转最长 15 分钟）
    aliveRef.current = false;
    adaptCtl.current?.abort();
    pollTimers.current.forEach((iv) => clearInterval(iv));
    pollTimers.current.clear();
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    return cleanupPublishActivity;
  }, [cleanupPublishActivity]);

  // 登录态 + 可选媒体列表
  useEffect(() => {
    fetchAccounts().then(setAccounts).catch(() => { /* 忽略 */ });
    fetchOutputs().then((roots) => {
      const files: OutputFile[] = [];
      const walk = (n: OutputFile) => {
        if (n.type === 'file') { if (n.kind === 'image' || n.kind === 'video') files.push(n); return; }
        for (const c of n.children || []) walk(c);
      };
      roots.forEach(walk);
      files.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
      setMediaFiles(files);
    }).catch(() => { /* 忽略 */ });
  }, []);

  useEffect(()=>{
    let active=true;
    productionRequest<LibraryWork[]>('library').then(rows=>{if(active){setWorks(rows);if(source)setTitle((previous:string)=>previous||rows.find(w=>w.artifact_id===source.output_id)?.title||'');}}).catch(e=>{if(active)setMediaError(e.message);});
    if(source)publicationCall<Publication[]>(`?work_id=${encodeURIComponent(source.work_id)}`,undefined,'GET').then(rows=>{if(active){const current=rows.filter(r=>r.output_id===source.output_id);setRecords(Object.fromEntries(current.map(r=>[r.platform||'bilibili',r])));setSavedContents(Object.fromEntries(current.map(r=>[r.platform||'bilibili',JSON.stringify(r.content)])));};}).catch(e=>{if(active)setMediaError(e.message);});
    return()=>{active=false;};
  },[source]);
  const runCover=async(fn:()=>Promise<void>)=>{if(coverBusy)return;setCoverBusy(true);try{await fn();}catch(e){showToast((e as Error).message);}finally{setCoverBusy(false);}};
  const updateRecord=(value:Publication)=>setRecords(r=>({...r,[value.platform||'bilibili']:value}));
  const prepare=async(key:string)=>{
    if(!source)return;
    const d=await publicationCall<Publication>('/prepare',{...source,platform:key});
    setSavedContents(old=>({...old,[key]:JSON.stringify(d.content)}));
    if(d.state==='draft'&&d.revision===1&&!records[key])updateRecord({...d,content:{...d.content,title:title||d.content.title,body:overrides[key]??body,tags:tags.split(/[,，]/).map((t:string)=>t.trim()).filter(Boolean)}});else updateRecord(d);
  };
  const saveRecord=async(key:string)=>{
    const d=records[key];if(!d)return;
    const saved=await publicationCall<Publication>(`/${d.id}`,{revision:d.revision,content:d.content},'PUT');
    updateRecord(saved);setSavedContents(old=>({...old,[key]:JSON.stringify(saved.content)}));
  };
  const copyCover=async(from:string)=>{
    const d=records[from],cover=source?d?.content.cover:covers[from];if(!cover)return;
    const targets=platforms.filter(k=>k!==from&&(!source||records[k]?.state==='draft')&&['xiaohongshu','douyin','kuaishou','weixin-channels','bilibili','wechat-oa'].includes(k));

    if(!targets.length){showToast('没有其他可编辑的平台草稿');return;}
    if(!source){setCovers(old=>({...old,...Object.fromEntries(targets.map(k=>[k,cover]))}));return;}
    const res=await fetch(publicationCoverURL(d.id,cover.digest));if(!res.ok)throw new Error('封面读取失败');const blob=await res.blob();
    for(const key of targets){const target=records[key];if(!target||target.state!=='draft')continue;
      const data=new FormData();data.append('revision',String(target.revision));data.append('file',blob,'cover.jpg');
      const next=await productionRequest<Cover>(`publications/${target.id}/covers/upload`,{method:'POST',body:data});
      updateRecord({...target,content:{...target.content,cover:next}});
    }
    showToast('已应用到可编辑的平台，请分别保存草稿');
  };
  const loginOf = (key: string) => accounts.find((a) => a.platform === key)?.loggedIn ?? false;

  const toggle = (k: string) =>
    setPlatforms((prev) => prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]);
  const showToast = (m: string) => { setToast(m); setTimeout(() => setToast(''), 2800); };
  const effective = (k: string) => source&&records[k]?records[k].content.body:overrides[k] ?? body;
  const empty = !source&&!title.trim() && !body.trim();
  const isVideoPath = (p: string) => /\.(mp4|mov|flv|mkv|avi|webm|m4v|wmv|ts|mpe?g)$/i.test(p);
  const toggleMedia = (path: string) =>
    setSelectedMedia((prev) => {
      if (prev.includes(path)) return prev.filter((x) => x !== path);
      // 通用规则：图片和视频不能同时；视频一次只发一个
      if (isVideoPath(path)) {
        if (prev.length && !prev.every(isVideoPath)) { showToast('图片和视频不能同时发布，请先取消已选图片'); return prev; }
        return [path]; // 视频单选
      }
      if (prev.some(isVideoPath)) { showToast('图片和视频不能同时发布，请先取消已选视频'); return prev; }
      return [...prev, path]; // 图片可多选（图文）
    });

  // A. 智能一稿多改（流式：逐字改写，直接流进每个平台卡片）
  const adapt = () => {
    if (empty || platforms.length === 0 || adapting) return;
    const sel = PLATFORMS.filter((p) => platforms.includes(p.key));
    const prompt =
      `请执行 /skill-content-repurposing：把下面这条内容改编到这些平台：${sel.map((p) => p.label).join('、')}。` +
      `务必参考该 SKILL 的 platform-specs 与改写配方，贴合各平台原生格式、语气与字数。\n` +
      `【硬性要求】输出各平台“可直接复制发布的纯文本正文”，禁止任何 Markdown 语法：不要 **加粗**、# 标题、---、表格、代码块、编号列表符号；` +
      `小红书可用 emoji 和 #话题标签，按平台习惯自然分行即可。\n` +
      `严格只按下面格式输出、每个平台之间用分隔线，不要任何额外说明：\n` +
      sel.map((p) => `===${p.label}===\n<该平台纯文本正文>`).join('\n') +
      `\n\n原始内容：\n标题：${title}\n正文：${body}`;

    setAdapting(true);
    let acc = '';
    const base = { ...overrides };
    adaptCtl.current = streamChat(
      prompt, persona, `adapt-${Date.now()}`,
      (chunk) => {                       // 逐字：实时解析并流进对应平台卡片
        acc += chunk;
        const map = parseSections(acc);
        const next = { ...base };
        for (const [label, text] of Object.entries(map)) {
          const key = LABEL2KEY[label];
          if (key && platforms.includes(key)) next[key] = text;
        }
        setOverrides(next);
        if(source)setRecords(previous=>Object.fromEntries(Object.entries(previous).map(([key,d])=>[key,next[key]!=null&&d.state==='draft'?{...d,content:{...d.content,body:next[key]}}:d])));
      },
      () => {                            // 完成
        const hit = Object.keys(parseSections(acc)).length;
        setAdapting(false);
        showToast(hit ? `已生成 ${hit} 个平台版本` : '未能解析，可重试');
      },
      () => { setAdapting(false); showToast('改写失败，请重试'); },
    );
  };
  const stopAdapt = () => { adaptCtl.current?.abort(); setAdapting(false); };

  const performPrecheck = async () => {
    const prompt =
      `你是社媒发布审核助手。针对下面这条待发内容做两项检查，用简洁中文分点输出：\n` +
      `1. **合规风险**：是否含极限词/医疗功效/敏感或违规表述，列出问题词+替换建议；无则写"未见明显风险"。\n` +
      `2. **标题/钩子**：给标题打 1-10 分，并给 1-2 个更好的备选。\n` +
      `最后一行给「✅可发 / ⚠️建议修改」结论。\n\n待检内容：\n标题：${title}\n正文：${body}`;
    const content = `待发布内容：\n标题：${title}\n正文：${body}`;
    const [general, personaResult] = await Promise.all([
      runAgent(prompt),
      persona ? executeSkill('persona-check', content, persona) : Promise.resolve(null),
    ]);
    return `${general.response}\n\n---\n\n## 人设一致性\n\n${personaResult?.response || '未选择画像，已跳过人设一致性检查。'}`;
  };

  // C. 发布前一键预检
  const check = async () => {
    if (empty) return;
    setChecking(true); setCheckResult('');
    try {
      setCheckResult(await performPrecheck());
    } catch (e) {
      setCheckResult(e instanceof Error ? e.message : '预检失败');
    } finally { setChecking(false); }
  };

  // D. 一键发布（真发布，二次确认）
  const publishAll = async () => {
    if (empty || publishing || checking) return;
    const targets = PLATFORMS.filter((p) => batch.includes(p.key) && PUBLISHABLE.has(p.key));
    if (targets.length === 0) {
      showToast('所选平台暂不支持一键发布');
      return;
    }
    setConfirming(false);

    setPublishing(true);
    for (const t of targets) {
      if(source){
        const d=records[t.key];
        if(!d){setPub(r=>({...r,[t.key]:{status:'fail',msg:'请先准备并保存此平台草稿'}}));continue;}
        if(d.state!=='draft'){setPub(r=>({...r,[t.key]:{status:'ok',msg:publicationStatus(d)}}));continue;}
        setPub(r=>({...r,[t.key]:{status:'publishing',msg:'正在执行原发布器…'}}));
        try{const latest=await publicationCall<Publication>(`/${d.id}`,undefined,'GET');
          if(JSON.stringify(latest.content)!==JSON.stringify(d.content)||latest.revision!==d.revision)throw new Error('草稿未保存或已变化，请保存后重新确认');
          const result=await publicationCall<Publication>(`/${d.id}/submit`,{revision:d.revision,confirmation_hash:d.confirmation_hash});
          updateRecord(result);setPub(r=>({...r,[t.key]:{status:'ok',msg:publicationStatus(result)}}));
        }catch(e){setPub(r=>({...r,[t.key]:{status:'fail',msg:(e as Error).message}}));}continue;
      }
      if (!loginOf(t.key)) {
        setPub((r) => ({ ...r, [t.key]: { status: 'fail', msg: '未登录 · 去账号页登录' } }));
        continue;
      }
      if (MEDIA_REQUIRED.has(t.key) && selectedMedia.length === 0) {
        setPub((r) => ({ ...r, [t.key]: { status: 'fail', msg: '需附带图片/视频' } }));
        continue;
      }
      if (VIDEO_ONLY.has(t.key) && !selectedMedia.some((p) => VIDEO_RE.test(p))) {
        setPub((r) => ({ ...r, [t.key]: { status: 'fail', msg: `${t.label}只能发视频，请从内容库选一个视频` } }));
        continue;
      }
      setPub((r) => ({ ...r, [t.key]: { status: 'publishing', msg: '发布中…可能需 1-2 分钟' } }));
      try {
        const res = await publishNow(t.key, { title, body: effective(t.key), media: selectedMedia, tags,persona,cover:covers[t.key],tid:t.key==='bilibili'?bilibiliTid:undefined });
        if (res.async) {
          // 抖音：异步发布，轮询状态；风控触发短信墙时弹输入框（条件触发，没触发就直接跑完）
          await pollAsyncPublish(t.key, t.label);
        } else {
          setPub((r) => ({
            ...r,
            [t.key]: res.ok
              ? { status: 'ok', msg: '已发布 ✅' }
              : { status: 'fail', msg: res.detail || res.message || '发布失败' },
          }));
        }
      } catch (e) {
        setPub((r) => ({ ...r, [t.key]: { status: 'fail', msg: e instanceof Error ? e.message : '发布失败' } }));
      }
    }
    setPublishing(false);
    showToast('发布流程结束，见各平台卡片状态');
  };

  // 异步发布轮询（抖音）：直到 success/error；遇 sms_required/verifying 弹短信窗口
  const pollAsyncPublish = (key: string, label: string) => new Promise<void>((resolve) => {
    const started = Date.now();
    const iv = setInterval(async () => {
      if (!aliveRef.current) { clearInterval(iv); pollTimers.current.delete(iv); resolve(); return; }
      if (Date.now() - started > 15 * 60 * 1000) {   // 15min 兜底
        clearInterval(iv); pollTimers.current.delete(iv); setPubSms(null);
        setPub((r) => ({ ...r, [key]: { status: 'fail', msg: '发布超时' } }));
        resolve(); return;
      }
      let s;
      try { s = await publishStatus(key); } catch { return; }  // 单次失败忽略
      if (s.state === 'sms_required' || s.state === 'verifying') {
        setPubSms({ platform: key, name: label, state: s.state, message: s.message });
        setPub((r) => ({ ...r, [key]: { status: 'publishing', msg: s.message || '需短信验证' } }));
      } else if (s.state === 'success') {
        clearInterval(iv); pollTimers.current.delete(iv); setPubSms(null);
        setPub((r) => ({ ...r, [key]: { status: 'ok', msg: '已发布 ✅' } }));
        resolve();
      } else if (s.state === 'error') {
        clearInterval(iv); pollTimers.current.delete(iv); setPubSms(null);
        setPub((r) => ({ ...r, [key]: { status: 'fail', msg: s.message || '发布失败' } }));
        resolve();
      } else {
        setPub((r) => ({ ...r, [key]: { status: 'publishing', msg: s.message || '发布中…' } }));
      }
    }, 2500);
    pollTimers.current.add(iv);
  });

  const submitPubSms = async () => {
    if (!pubSms) return;
    const code = pubSmsCode.replace(/\D/g, '');
    if (code.length < 4) { showToast('验证码应为 4-6 位数字'); return; }
    setPubSmsBusy(true);
    try {
      await submitPublishSms(pubSms.platform, code);
      setPubSmsCode('');
      setPubSms((p) => p && ({ ...p, state: 'verifying', message: '正在验证验证码…' }));
    } catch (e) {
      showToast(e instanceof Error ? e.message : '提交失败');
    } finally {
      setPubSmsBusy(false);
    }
  };

  useEffect(()=>{
    if(!source||!publishing||!batch.includes('douyin'))return;
    let active=true;
    const timer=setInterval(()=>void publishStatus('douyin').then(status=>{if(active&&(status.state==='sms_required'||status.state==='verifying'))setPubSms({platform:'douyin',name:'抖音',state:status.state,message:status.message});}).catch(()=>{}),2500);
    return()=>{active=false;clearInterval(timer);setPubSms(null);};
  },[source,publishing,batch]);

  const copyFor = (key: string) => {
    const heading=source?records[key]?.content.title:title;
    const text = (heading ? heading + '\n\n' : '') + effective(key);
    navigator.clipboard?.writeText(text);
    setCopied(key); setTimeout(() => setCopied(''), 1400);
  };
  const addToCalendar = async (key: string) => {
    if (empty) return;
    // 用本地日期（日历页按本地渲染）：toISOString 是 UTC，东八区 0-8 点会落到「昨天」
    const d = new Date();
    const date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    await createSchedule({
      title: title.trim() || effective(key).slice(0, 20), date,
      platform: PLATFORMS.find((p) => p.key === key)?.label || '', time: '', status: 'draft', note: effective(key),
    });
    showToast('已存为草稿并加入今天的日历');
  };

  const hasUnsaved=!!source&&platforms.some(key=>records[key]?.state==='draft'&&JSON.stringify(records[key].content)!==savedContents[key]);
  const canPublish = platforms.some((k) => PUBLISHABLE.has(k));

  return (
    <div className="publish-page">
      <div className="publish-editor">
        <h1 className="page-title"><IconPublish size={21} /> 发布中心</h1>
        <p className="page-subtitle">选择成片或文件，再按平台编辑和预览。已有投稿请查看原发布记录。</p>

        {source&&<div className="notice"><strong>{works.find(w=>w.work_id===source.work_id)?.title||'所选成片'} · 版本 {works.find(w=>w.artifact_id===source.output_id)?.output_revision||'已选定'}</strong><video controls preload="metadata" className="publication-video" src={artifactURL(source.output_id)}/><p>各平台稿件独立保存。已有投稿保持原记录。</p></div>}
        {mediaError&&<p role="alert" className="pv-pubstate fail">{mediaError}</p>}
        <label className="field-label">{source?'新平台草稿标题（母版）':'标题'}</label>
        <input className="field" value={title} placeholder="标题（部分平台需要）"
          onChange={(e) => setTitle(e.target.value)} />
        <label className="field-label">正文（母版）{source&&' · 创建平台草稿时使用；已创建的稿件在右侧编辑并保存'}</label>
        <textarea className="field" style={{ minHeight: 180 }} value={body}
          placeholder="写下你的内容，右侧按各平台规则实时预览；点「一键适配」让 AI 分平台改写…"
          onChange={(e) => setBody(e.target.value)} />

        <label className="field-label">话题标签 <span style={{ color: 'var(--text-secondary)', fontWeight: 400, fontSize: 12 }}>（逗号分隔，如「AI,职场,干货」；小红书会用 # 联想真正绑定话题）</span></label>
        <input className="field" value={tags} placeholder="AI,职场,干货"
          onChange={(e) => setTags(e.target.value)} />

        <label className="field-label">发布平台</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {PLATFORMS.map((p) => (
            <button key={p.key} className={`chip ${platforms.includes(p.key) ? 'active' : ''}`}
              onClick={() => toggle(p.key)}>{p.label}</button>
          ))}
        </div>

        <label className="field-label" style={{ marginTop: 14 }}>
          媒体附件 {selectedMedia.length > 0 && <span className="pv-badge">{selectedMedia.length} 个</span>}
          <span style={{ color: 'var(--text-secondary)', fontWeight: 400, fontSize: 12 }}>（小红书/抖音/快手/微信视频号/B站必需，从内容库选；抖音、视频号、B站须为视频）</span>
        </label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button className="btn btn-sm" onClick={() => setShowPicker((v) => !v)}>
            <IconSkills size={13} /> {showPicker ? '收起' : '选择媒体'}
          </button>
          {!source&&selectedMedia.map((path) => (
            <div key={path} className="media-chip" onClick={() => toggleMedia(path)} title="点击移除">
              {mediaFiles.find((f) => f.path === path)?.kind === 'image'
                ? <img src={mediaUrl(path)} alt="" /> : <span className="media-vid">🎬</span>}
              <span className="media-x">×</span>
            </div>
          ))}
        </div>
        {showPicker && (
          <><div className="publish-actions">{(['all','work','file'] as const).map(k=><button className={`chip ${filter===k?'active':''}`} key={k} onClick={()=>setFilter(k)}>{({all:'全部',work:'成片',file:'文件'})[k]}</button>)}<input className="field" aria-label="搜索媒体" placeholder="搜索标题或文件名" value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="media-grid">
            {filter!=='file'&&works.filter(w=>w.artifact_id&&w.title.includes(query)).map(w=><button className={`media-cell ${source?.output_id===w.artifact_id?'sel':''}`} aria-pressed={source?.output_id===w.artifact_id} title={`${w.title} · 版本 ${w.output_revision}`} key={w.work_id} onClick={()=>openPublishSource(w.work_id,w.artifact_id!)}><video preload="metadata" src={artifactURL(w.artifact_id!)}/><span>{w.title} · 版本 {w.output_revision}</span></button>)}
            {mediaFiles.length === 0 && (filter==='file'||works.length===0) && <div className="dash-empty">暂无普通图片/视频文件</div>}
            {mediaFiles.filter(f=>filter!=='work'&&f.name.includes(query)).map((f) => (
              <div key={f.path}
                className={`media-cell ${selectedMedia.includes(f.path) ? 'sel' : ''}`}
                onClick={() => {if(source){showToast('请先点击返回文件草稿，再选择文件');return;}toggleMedia(f.path);}} title={f.path}>
                {f.kind === 'image'
                  ? <img src={mediaUrl(f.path)} alt={f.name} loading="lazy" />
                  : <span className="media-vid">🎬<br />{f.name.slice(0, 12)}</span>}
                {selectedMedia.includes(f.path) && <span className="media-check">✓</span>}
              </div>
            ))}
          </div></>
        )}

        <div className="publish-actions">
          {adapting ? (
            <button className="btn btn-sm" onClick={stopAdapt}><IconStop size={13} /> 停止生成</button>
          ) : (
            <button className="btn btn-sm btn-primary" disabled={empty || platforms.length === 0} onClick={adapt}>
              <IconSkills size={14} /> 一键适配各平台
            </button>
          )}
          <button className="btn btn-sm" disabled={empty || checking || adapting} onClick={check}>
            <IconCheck size={14} /> {checking ? '预检中…' : '发布前预检'}
          </button>
          <button className="btn btn-sm" disabled={empty} onClick={() => addToCalendar(platforms[0] || 'xiaohongshu')}>
            <IconCalendar size={14} /> 存草稿并排期
          </button>
          <button className="btn btn-sm btn-primary" disabled={empty || publishing || checking || coverBusy || hasUnsaved || !canPublish}
            title={canPublish ? '真实发布到已登录平台' : '所选平台无一键发布（B站走终端 biliup）'}
            onClick={()=>{setBatch(platforms.filter(key=>!source||records[key]?.state==='draft'));setConfirming(true);}}>
            <IconPublish size={14} /> {publishing ? '发布中…' : '一键发布'}
          </button>
          <button className="btn btn-sm btn-ghost" disabled={empty || adapting}
            onClick={() => { setTitle(''); setBody(''); setTags(''); setOverrides({}); setCheckResult(''); setPub({}); showToast('已清空'); }}>
            <IconTrash size={13} /> 清空
          </button>
        </div>
        {adapting && <div className="adapt-hint"><span className="live-pulse" />AI 正在逐字改写各平台版本…可随时停止。</div>}
        {hasUnsaved&&<p className="publish-saved-note" role="status">有平台稿件尚未保存，请先保存后查看最终确认。</p>}
        <p className="publish-saved-note">草稿已自动保存，切换页面/刷新回来内容都在。一键发布仅对「已登录 + 媒体齐全」的平台生效。</p>
        {checkResult && (
          <div className="panel" style={{ marginTop: 14 }}>
            <div className="panel-title"><IconCheck size={14} /> 发布前预检</div>
            <div className="skill-body-md" dangerouslySetInnerHTML={{ __html: renderMarkdown(checkResult) }} />
          </div>
        )}
      </div>

      <div className="publish-previews">
        {platforms.length === 0 && <div className="dash-empty">选择至少一个平台查看预览</div>}
        {PLATFORMS.filter((p) => platforms.includes(p.key)).map((p) => {
          const text = effective(p.key);
          const over = text.length > p.bodyLimit;
          const titleOver = p.titleLimit != null && title.length > p.titleLimit;
          const isEdit = editing === p.key;
          const record=records[p.key];
          const ps = pub[p.key];
          const publishable = PUBLISHABLE.has(p.key);
          const logged = loginOf(p.key);
          return (
            <div key={p.key} className={`card pv-card pv-${p.key}`}>
              <div className="pv-head">
                <span className="pv-plat">
                  {p.label}
                  {overrides[p.key] != null && <span className="pv-badge">AI 版</span>}
                  {publishable && (logged
                    ? <span className="pv-badge pv-badge-ok">已登录</span>
                    : <span className="pv-badge">未登录</span>)}
                </span>
                <span className={`pv-count ${over ? 'over' : ''}`}>{text.length}/{p.bodyLimit}</span>
              </div>
              <div className="pv-body">
                {p.titleLimit != null && (
                  <div className={`pv-title ${titleOver ? 'over' : ''}`}>{(source?record?.content.title:title) || <span className="pv-ph">标题…</span>}</div>
                )}
                {isEdit
                  ? <textarea className="field" style={{ minHeight: 120 }} value={text} autoFocus
                      onChange={(e) => {if(source&&record)updateRecord({...record,content:{...record.content,body:e.target.value}});else setOverrides((o) => ({ ...o, [p.key]: e.target.value }));}} />
                  : <div className="pv-text">{text || <span className="pv-ph">正文预览…</span>}{adapting && overrides[p.key] != null && <span className="streaming-cursor" />}</div>}
              </div>
              {source?<div className="publication-details">
                {!record?<button className="btn btn-sm" disabled={coverBusy||!['bilibili','xiaohongshu','douyin','kuaishou','weixin-channels'].includes(p.key)} onClick={()=>void runCover(()=>prepare(p.key))}>准备此平台草稿</button>:<>
                  <p>{publicationStatus(record)}</p>
                  {record.state==='draft'?<>
                    <label className="field-label">此平台标题<input className="field" value={record.content.title} onChange={e=>updateRecord({...record,content:{...record.content,title:e.target.value}})}/></label>
                    <label className="field-label">标签<input className="field" value={record.content.tags.join(',')} onChange={e=>updateRecord({...record,content:{...record.content,tags:e.target.value.split(/[,，]/).map(x=>x.trim()).filter(Boolean)}})}/></label>
                    {p.key==='bilibili'&&<><BilibiliPartition value={record.content.tid} catalog={partitions.catalog} refresh={partitions.refresh} disabled={record.state!=='draft'||coverBusy||publishing} onChange={tid=>updateRecord({...record,content:{...record.content,tid}})}/><label className="field-label">稿件类型<select className="field" value={record.content.copyright} onChange={e=>updateRecord({...record,content:{...record.content,copyright:Number(e.target.value)}})}><option value={1}>自制</option><option value={2}>转载</option></select></label>{record.content.copyright===2&&<input className="field" aria-label="转载来源" value={record.content.source} onChange={e=>updateRecord({...record,content:{...record.content,source:e.target.value}})}/>}</>}
                    <PublicationCover draft={record} cover={record.content.cover} disabled={coverBusy||publishing} onChange={cover=>updateRecord({...record,content:{...record.content,cover}})} run={runCover}/>
                    <p>账号：{record.content.account?.name||'尚未读取'}</p><div className="publish-actions"><button className="btn btn-sm" disabled={coverBusy} onClick={()=>void runCover(async()=>updateRecord({...record,content:{...record.content,account:await publicationCall(`/account?platform=${p.key}`)}}))}>读取实际登录账号</button><button className="btn btn-sm" disabled={coverBusy} onClick={()=>void runCover(()=>saveRecord(p.key))}>保存此平台草稿</button>{record.content.cover&&<><button className="btn btn-sm" disabled={coverBusy} onClick={()=>void runCover(()=>copyCover(p.key))}>将封面应用到所选平台</button><small className="page-subtitle">将替换其他可编辑已选平台的封面，之后分别保存。</small></>}</div>
                    <details><summary>随稿素材署名</summary><p className="pv-text">{record.content.credits||'无附加署名'}</p></details>
                  </>:null}
                  <button className="btn btn-ghost btn-sm" onClick={()=>openPublicationDraft(record.id)}>查看原发布记录</button>
                </>}
                {!['bilibili','xiaohongshu','douyin','kuaishou','weixin-channels'].includes(p.key)&&<p>此平台保留原图文流程；请返回文件草稿准备适用内容。</p>}
              </div>:['bilibili','xiaohongshu','douyin','kuaishou','weixin-channels','wechat-oa'].includes(p.key)&&<div className="publication-details">{p.key==='bilibili'&&<BilibiliPartition value={bilibiliTid} onChange={setBilibiliTid} catalog={partitions.catalog} refresh={partitions.refresh} disabled={coverBusy||publishing}/>}<p>账号：{fileAccounts[p.key]||'当前登录账号（身份未核验）'}</p><button className="btn btn-sm" disabled={coverBusy} onClick={()=>void runCover(async()=>{const a=await accountWhoami(p.key,true);if(!a.loggedIn)throw new Error('请先到账号页登录');setFileAccounts(old=>({...old,[p.key]:a.name||'平台未返回昵称'}));})}>读取实际登录账号</button><PublicationCover fileVideo={selectedMedia.find(isVideoPath)} cover={covers[p.key]} disabled={coverBusy||publishing} onChange={cover=>setCovers(old=>({...old,[p.key]:cover}))} run={runCover}/>{covers[p.key]&&<><button className="btn btn-sm" disabled={coverBusy} onClick={()=>void runCover(()=>copyCover(p.key))}>将封面应用到所选平台</button><small className="page-subtitle">将替换其他可编辑已选平台的封面，之后分别保存。</small></>}</div>}
              {ps && (
                <div className={`pv-pubstate ${ps.status}`}>
                  {ps.status === 'publishing' && <span className="live-pulse" />}
                  {ps.status === 'ok' ? '✅ ' : ps.status === 'fail' ? '⚠️ ' : ''}{ps.msg}
                </div>
              )}
              <div className="pv-foot">
                <span className="pv-hint">{p.hint}{over ? ' · 已超字数' : ''}</span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button className="pv-copy" disabled={!!source&&record?.state!=='draft'} onClick={() => setEditing(isEdit ? null : p.key)}>
                    <IconEdit size={13} />{isEdit ? '完成' : '编辑'}
                  </button>
                  <button className="pv-copy" onClick={() => copyFor(p.key)}>
                    {copied === p.key ? <IconCheck size={13} /> : <IconCopy size={13} />}{copied === p.key ? '已复制' : '复制'}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {confirming&&<div className="overlay"><div className="modal publication-confirm" role="dialog" aria-modal="true" aria-labelledby="multi-publish-confirm"><h2 id="multi-publish-confirm">确认本次发布</h2>{platforms.map(key=>{const d=records[key],c=source?d?.content.cover:covers[key];return <section key={key}><h3>{PLATFORMS.find(p=>p.key===key)?.label}</h3><p>{source?(!d?'此平台尚未准备适用稿件，不执行':d.state!=='draft'?'保留原记录，不重复投稿':`成片版本 ${d.output_revision} · ${d.content.account?.name||'尚未读取账号'}${key==='bilibili'?` · 分区 ${partitionLabel(partitions.catalog,d.content.tid)} · ${d.content.copyright===1?'自制':'转载'}`:''}`):`所选文件 · ${fileAccounts[key]||'当前登录账号（身份未核验）'}`}</p><strong>{source?d?.content.title:title}</strong><p className="pv-text">{effective(key)}</p>{c?<img className="publication-cover-image" alt="本次投稿确认封面" src={source?publicationCoverURL(d.id,c.digest):fileCoverURL(c.digest)}/>:<p>封面：平台默认处理</p>}{!source&&key==='bilibili'&&<p>分区：{partitionLabel(partitions.catalog,bilibiliTid)}</p>}{!source&&<p>媒体：{selectedMedia.join('、')||'尚未选择'}</p>}{d&&<details><summary>随稿署名</summary><p>{d.content.credits}</p></details>}</section>;})}<p>确认后会执行所列可用平台的原发布器。平台结果分别保留。</p><div className="publish-actions"><button className="btn" autoFocus onClick={()=>setConfirming(false)}>返回修改</button><button className="btn btn-primary" disabled={publishing||coverBusy||batch.length===0} onClick={()=>void publishAll()}>确认发布</button></div></div></div>}
      {toast && <div className="toast ok"><span className="toast-icon">✓</span>{toast}</div>}

      {pubSms && (
        <div className="overlay" onClick={(e) => { if (e.target === e.currentTarget) setPubSms(null); }}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 380 }}>
            <h3 style={{ margin: '0 0 4px' }}>发布验证 · {pubSms.name}</h3>
            <p style={{ fontSize: 13, color: /错误|过期|失败|重新|未完成|不正确|失效/.test(pubSms.message || '') ? 'var(--red)' : 'var(--text-secondary)' }}>
              {pubSms.message || '平台风控要求短信验证，验证码已发到你手机，请输入：'}
            </p>
            {pubSms.state === 'verifying' ? (
              <div className="dash-empty" style={{ padding: 16 }}>正在验证验证码…</div>
            ) : (
              <>
                <input inputMode="numeric" autoFocus
                  placeholder="请输入手机收到的验证码" value={pubSmsCode}
                  onChange={(e) => setPubSmsCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                  onKeyDown={(e) => { if (e.key === 'Enter') submitPubSms(); }}
                  style={{ width: '100%', boxSizing: 'border-box', textAlign: 'center',
                    letterSpacing: 6, fontSize: 20, padding: '10px 12px', margin: '4px 0 10px',
                    border: '1px solid var(--border)', borderRadius: 8 }} />
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn btn-sm btn-ghost" onClick={() => setPubSms(null)}>关闭</button>
                  <button className="btn btn-sm btn-primary" disabled={pubSmsBusy} onClick={submitPubSms}>
                    {pubSmsBusy ? '提交中…' : '提交验证码'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
