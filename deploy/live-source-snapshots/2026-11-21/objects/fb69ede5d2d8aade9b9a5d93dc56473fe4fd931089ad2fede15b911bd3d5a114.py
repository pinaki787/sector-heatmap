"""Render the repository's small Markdown functional guide without dependencies."""
import html
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs/user-functional-guide.md'
TARGET=SOURCE.with_suffix('.html')


def inline(text):
    text=html.escape(text)
    text=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',text)
    text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',text)


def render():
    sections=[];toc=[]
    for block in SOURCE.read_text().strip().split('\n\n'):
        lines=block.splitlines()
        match=re.match(r'^(#{1,3}) (.+)$',lines[0])
        if match and len(lines)==1:
            level=len(match[1]);title=match[2];anchor=re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-')
            sections.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
            if level==2:toc.append(f'<a href="#{anchor}">{inline(title)}</a>')
        elif all(re.match(r'^\d+\. ',line) for line in lines):
            sections.append('<ol>'+''.join('<li>'+inline(re.sub(r'^\d+\. ','',line))+'</li>' for line in lines)+'</ol>')
        elif all(line.startswith('- ') for line in lines):
            sections.append('<ul>'+''.join('<li>'+inline(line[2:])+'</li>' for line in lines)+'</ul>')
        else:sections.append('<p>'+inline(' '.join(lines))+'</p>')
    style='''body{margin:0;background:#f3f5f9;color:#243047;font:16px/1.7 system-ui,-apple-system,sans-serif}header{background:#14233d;color:#fff;padding:24px max(24px,calc((100vw - 1000px)/2))}header strong{font-size:22px}nav{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px}nav a{color:#b8d9ff;font-size:14px}main{max-width:1000px;margin:32px auto;padding:28px 44px;background:#fff;border:1px solid #dce2ec;border-radius:12px}h1{font-size:34px;line-height:1.25;color:#14233d}h2{margin-top:42px;padding-top:16px;border-top:2px solid #dde8f6;color:#1c416e;font-size:26px}h3{margin-top:30px;font-size:21px;color:#273e60}a{color:#1b5d9e}li{margin:8px 0}strong{font-weight:650}code{background:#edf1f7;padding:2px 5px;border-radius:3px}footer{max-width:1000px;margin:24px auto 40px;color:#64748b;font-size:13px;padding:0 24px}@media(max-width:700px){main{margin:12px;padding:22px}h1{font-size:28px}}'''
    TARGET.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Sector Pulse User Functional Guide</title><style>'+style+'</style></head><body><header><strong>Sector Pulse · User functional guide</strong><nav>'+''.join(toc)+'</nav></header><main>'+''.join(sections)+'</main><footer>Source: <a href="user-functional-guide.md">user-functional-guide.md</a> · Updated 8 October 2026 · No trading action is performed by this guide.</footer></body></html>')
    return TARGET

if __name__=='__main__':print(render())
