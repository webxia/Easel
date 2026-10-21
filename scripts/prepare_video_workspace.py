#!/usr/bin/env python3
"""Prepare reviewed video instructions and an uninstalled config patch. No service mutation."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from easel.video_workspace import prepare_workspace, main_pipeline_tools

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--destination',type=Path,required=True)
    parser.add_argument('--patch-file',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True,
                        help='只读现有 OpenClaw 配置；输出不含原配置或凭证')
    args=parser.parse_args()
    if args.patch_file.exists():parser.error('补丁文件已存在，不覆盖')
    repo=Path(__file__).resolve().parents[1]
    config=json.loads(args.config.read_text())
    try:
        tools=main_pipeline_tools(config['agents']['entries']['main']['tools'])
    except (KeyError,ValueError) as error:
        parser.error(str(error))
    entry=prepare_workspace(repo,args.destination)
    # Never replace main's workspace, skills or general tool policy.
    # A coding profile intersects allow and drops the native plugin tools.
    # Keep the explicit allow/deny and other policy fields; do not use a wildcard.
    patch={'agents':{'entries':{'main':{'tools':tools}}},
        'plugins':{'load':{'paths':[str(repo/'agents/plugins/easel-work')]},
            'entries':{'easel-work':{'enabled':True,'hooks':{'allowConversationAccess':True,'allowPromptInjection':True},
                'config':{'baseUrl':'http://127.0.0.1:7860','token':'REPLACE_WITH_SEPARATE_BRIDGE_CREDENTIAL','agentId':'main','protocolVersion':2}}}}}
    args.patch_file.parent.mkdir(parents=True,exist_ok=True)
    with args.patch_file.open('x') as output:json.dump(patch,output,ensure_ascii=False,indent=2)
    args.patch_file.chmod(0o600)
    print('已生成产品指令参考和main待合并补丁（full + 现有具名allow及九工具，保留deny）；须审阅原allow中此前被profile过滤的条目，保留原插件清单/凭证/模型/工作区/技能；未安装、未启动服务。')
