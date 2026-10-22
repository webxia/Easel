import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({ breaks: true, gfm: true });

/** 把 markdown 渲染成【已消毒】的 HTML。所有 dangerouslySetInnerHTML 都应走这里，防 XSS。 */
export function renderMarkdown(md: string): string {
  if (!md) return '';
  const raw = marked.parse(md) as string;
  const fragment = DOMPurify.sanitize(raw, { RETURN_DOM_FRAGMENT: true });
  // Model-authored HTML may omit controls. Keep sanitization authoritative;
  // playback behavior belongs to the host, not to generated markup.
  fragment.querySelectorAll('video, audio').forEach(media => {
    media.setAttribute('controls', '');
    media.setAttribute('preload', 'metadata');
    media.removeAttribute('autoplay');
  });
  const container = document.createElement('div');
  container.appendChild(fragment);
  return container.innerHTML;
}
