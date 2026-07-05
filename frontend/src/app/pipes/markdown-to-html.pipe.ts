import { Pipe, PipeTransform } from '@angular/core';

/** Minimal safe markdown → HTML converter (no external deps). */
@Pipe({ name: 'markdownToHtml', standalone: true, pure: true })
export class MarkdownToHtmlPipe implements PipeTransform {
  transform(md: string): string {
    if (!md) return '';
    let html = md
      // Headings
      .replace(/^### (.+)$/gm, '<h3 class="text-sm font-bold text-white mt-4 mb-1">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-base font-bold text-white mt-5 mb-2">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-lg font-bold text-white mt-6 mb-2">$1</h1>')
      // Bold + Italic
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // GitHub alerts
      .replace(/^> \[!NOTE\]\n> (.+)$/gm, '<div class="alert-note p-3 rounded border-l-4 border-blue-500 bg-blue-500/10 text-blue-300 text-xs my-2">$1</div>')
      .replace(/^> \[!WARNING\]\n> (.+)$/gm, '<div class="alert-warn p-3 rounded border-l-4 border-yellow-500 bg-yellow-500/10 text-yellow-300 text-xs my-2">$1</div>')
      .replace(/^> \[!CAUTION\]\n> (.+)$/gm, '<div class="alert-caution p-3 rounded border-l-4 border-red-500 bg-red-500/10 text-red-300 text-xs my-2">$1</div>')
      // Blockquotes
      .replace(/^> (.+)$/gm, '<blockquote class="border-l-2 border-gray-600 pl-3 text-gray-400 italic my-1">$1</blockquote>')
      // Code spans
      .replace(/`([^`]+)`/g, '<code class="bg-gray-800 text-mintaccent px-1 rounded text-xs font-mono">$1</code>')
      // Unordered lists
      .replace(/^\s*[-*] (.+)$/gm, '<li class="flex items-start gap-2 my-0.5"><span class="text-mintaccent flex-shrink-0 mt-1">▸</span><span>$1</span></li>')
      // Horizontal rules
      .replace(/^---$/gm, '<hr class="border-gray-800 my-3"/>')
      // Paragraphs — wrap lines that aren't already HTML tags
      .replace(/^(?!<)(.+)$/gm, '<p class="text-gray-300 my-1">$1</p>')
      // Wrap consecutive li tags
      .replace(/(<li[^>]*>[\s\S]*?<\/li>\s*)+/g, '<ul class="my-2 space-y-0.5">$&</ul>');

    return html;
  }
}
