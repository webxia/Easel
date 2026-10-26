"""Read-only follow-up guidance for cards and the existing result event."""
def output_guidance(artifact, accepted=False, known_failure=False, publication=False):
    if accepted and (not known_failure or artifact.get('creator_accepted')):
        return {'message':('已接受此版并保存到内容库。可查看原发布草稿或记录，继续修改或下载视频与署名。' if publication else '已接受此版并保存到内容库。可准备发布、继续修改或下载视频与署名；准备草稿不会自动投稿。'), 'can_accept':False,'can_publish':True}
    if artifact.get('manual_review_required'):
        visual=[q.get('findings',{}) for q in artifact.get('checks',[]) if q.get('findings',{}).get('scope')=='sampled_visual_only']
        conflict=bool(visual and visual[-1].get('review',{}).get('verdict')=='pass' and visual[-1].get('review',{}).get('findings'))
        lead=('抽样审片的结论与问题列表存在矛盾，暂不能认定画面有缺陷。可直接说“只复核这版审片结论，不重做视频”。' if conflict else '自动检查意见保留供审阅。' if known_failure else '')
        version='第'+str(artifact['output_revision'])+'版' if artifact.get('output_revision') else '此版'
        return {'message':lead+'技术检查通过，完整声音与语义仍待人工审片。要改画面，直接告诉我第几秒、哪个镜头以及想改成什么；要改口播，给出原句和替换句，我会先说明改稿、重配音与字幕调整范围。完整看过并确认画面、声音、字幕和同步都没问题后，再明确说“接受'+version+'”；接受不会自动发布。也可下载视频与署名。', 'can_accept':True,'can_publish':False}
    if known_failure:
        return {'message':'此版为待修预览。你可以先问“具体哪几秒、哪里有问题”，或直接描述要改的镜头、原句和替换要求；我会先说明本次修改范围，确认后再执行。可以下载视频与署名。', 'can_accept':False,'can_publish':False}
    if artifact.get('quality_state')=='passed':
        return {'message':'此版检查通过，请完整播放审阅。需要修改时，直接说第几秒的画面怎么改，或哪句口播换成什么；我会先说明修改范围。审阅画面、声音、字幕和同步后，可明确接受此版，再另行决定是否准备发布。也可下载视频与署名。', 'can_accept':True,'can_publish':False}
    return {'message':'此版尚不满足接受条件。可先问“还有哪项检查没完成、具体卡在哪里”，我会按当前结果说明能否复核或修订。也可播放预览、描述要改的地方，或下载视频与署名。','can_accept':False,'can_publish':False}
