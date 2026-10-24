import {partitionLabel,type Partition,type PartitionCatalog} from '../lib/bilibiliPartitions';
export default function BilibiliPartition({value,onChange,catalog,refresh,disabled=false}:{value:number;onChange:(tid:number)=>void;catalog:PartitionCatalog;refresh:()=>void;disabled?:boolean}){
 const leaves=(items:Partition[]):Partition[]=>items.flatMap(p=>p.children.length?leaves(p.children):[p]);
 const groups=catalog.groups;
 const present=leaves(groups).some(p=>p.id===value);
 return <div className="publication-partition">
  <label className="field-label">投稿分区<select className="field" value={value} disabled={disabled} onChange={e=>onChange(Number(e.target.value))}>
   {!present&&<option value={value}>{partitionLabel(catalog,value)}</option>}
   {groups.map(p=>p.children.length?<optgroup key={p.id} label={p.name}>{leaves(p.children).map(child=><option key={child.id} value={child.id}>{child.name}</option>)}</optgroup>:<option key={p.id} value={p.id}>{p.name}</option>)}
  </select></label>
  <p className="page-subtitle">{catalog.message}</p>
  {!disabled&&<><button className="btn btn-ghost btn-sm" type="button" onClick={refresh}>刷新分区</button><details><summary>手动填写分区编号</summary><label className="field-label">分区编号<input type="number" min="1" step="1" className="field" value={value} onChange={e=>{const n=Number(e.target.value);if(Number.isInteger(n)&&n>0)onChange(n);}}/></label></details></>}
 </div>;
}
