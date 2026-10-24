import {useEffect,useState} from 'react';
import {publicationCall} from './publicationApi';
export interface Partition {id:number;name:string;children:Partition[]}
export interface PartitionCatalog {groups:Partition[];source:string;message:string}
export const emptyPartitions:PartitionCatalog={groups:[],source:'loading',message:'正在读取投稿分区…'};
export function partitionLabel(catalog:PartitionCatalog,tid:number):string {
 const find=(items:Partition[],prefix:string):string|undefined=>{
  for(const item of items){const path=prefix?`${prefix} / ${item.name}`:item.name;
   if(item.id===tid)return path+(item.children.length?'（未细分）':'');
   const child=find(item.children,path);if(child)return child;
  }
 };
 return find(catalog.groups,'')||`原分区（编号 ${tid}）`;
}
export function useBilibiliPartitions(enabled:boolean){
 const [catalog,setCatalog]=useState<PartitionCatalog>(emptyPartitions);
 const [refresh,setRefresh]=useState(0);
 useEffect(()=>{if(!enabled)return;let active=true;
  publicationCall<PartitionCatalog>(`/partitions${refresh?'?refresh=true':''}`,undefined,'GET').then(value=>{if(active)setCatalog(value);}).catch(()=>{if(active)setCatalog({groups:[],source:'unavailable',message:'暂时无法读取分区，原选择保留；可刷新或手动填写。'});});
  return()=>{active=false;};
 },[enabled,refresh]);
 return {catalog,refresh:()=>setRefresh(n=>n+1)};
}
