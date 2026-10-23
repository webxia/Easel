"""Read-only follow-up guidance for cards and the existing result event."""
def output_guidance(artifact, accepted=False, known_failure=False, publication=False):
    if known_failure:
        return {'message':'此版为待修预览，请查看问题并提出修改；可以下载视频与署名。', 'can_accept':False,'can_publish':False}
    if accepted:
        return {'message':('已接受此版并保存到内容库。可查看原发布草稿或记录，继续修改或下载视频与署名。' if publication else '已接受此版并保存到内容库。可准备发布、继续修改或下载视频与署名；准备草稿不会自动投稿。'), 'can_accept':False,'can_publish':True}
    if artifact.get('manual_review_required'):
        return {'message':'技术检查通过，完整声音与语义仍待人工审片。请看完整片后提出修改或明确接受此版；也可先下载视频与署名。', 'can_accept':True,'can_publish':False}
    if artifact.get('quality_state')=='passed':
        return {'message':'此版检查通过，请完整播放审阅。可提出局部修改、接受此版或下载视频与署名；接受后可准备发布。', 'can_accept':True,'can_publish':False}
    return {'message':'此版尚不满足接受条件。可播放预览、提出修改或下载视频与署名。','can_accept':False,'can_publish':False}
