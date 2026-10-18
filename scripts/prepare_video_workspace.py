#!/usr/bin/env python3
"""Prepare reviewed video instructions and an uninstalled config patch. No service mutation."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from easel.video_workspace import prepare_workspace

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--patch-file',type=Path,required=True)
    args=parser.parse_args()
    if args.patch_file.exists():parser.error('补丁文件已存在，不覆盖')
    repo=Path(__file__).resolve().parents[1]
    entry=prepare_workspace(repo,args.destination)
    patch={'agents':{'entries':{'easel-video':{k:v for k,v in entry.items() if k in {'workspace','skills','tools'}}}},
        'plugins':{'allow':['easel-work'],'load':{'paths':[str(repo/'agents/plugins/easel-work')]},
            'entries':{'easel-work':{'enabled':True,'hooks':{'allowConversationAccess':True},'config':{'baseUrl':'http://127.0.0.1:7860','token':'REPLACE_WITH_SEPARATE_BRIDGE_CREDENTIAL','protocolVersion':2}}}}}
    args.patch_file.parent.mkdir(parents=True,exist_ok=True)
    with args.patch_file.open('x') as output:json.dump(patch,output,ensure_ascii=False,indent=2)
    args.patch_file.chmod(0o600)
    print('已生成受限工作区和待合并配置补丁；未安装、未改原配置、未启动服务。')
