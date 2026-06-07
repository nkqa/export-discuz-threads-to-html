import os
import re
import pymysql
import markdown
from datetime import datetime

# =========================
# 🔧 DB配置(输入你的数据库密码等信息)
# =========================
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "数据库用户名",
    "password": "你的密码",
    "database": "数据库名",
    "charset": "utf8mb4"
}

# =========================
# 📁 导出目录
# =========================
export_dir = input("请输入导出目录：").strip() or "./export"
os.makedirs(export_dir, exist_ok=True)

# =========================
# 🎨 spoiler资源（main）
# =========================
SPOILER_CSS = "https://cdn.jsdmirror.com/gh/nkqa/spoiler-html@main/1/spoiler.css"
SPOILER_JS  = "https://cdn.jsdmirror.com/gh/nkqa/spoiler-html@main/1/spoiler.js"

# =========================
# 🧹 数据清洗
# =========================
def sanitize(text):
    """移除 UTF-16 代理字符（\\ud800-\\udfff），避免 UnicodeEncodeError"""
    if not isinstance(text, str):
        return text
    return ''.join(c for c in text if ord(c) < 0xd800 or ord(c) > 0xdfff)

# =========================
# 🔗 附件CDN
# =========================
ATTACH_BASE = "https://static.mcneko.com/forum"
ATTACH_MAP = {}  # aid -> 附件相对路径，由 get_attach_map() 填充

# =========================
# 🧠 spoiler / hide
# =========================
def process_spoiler(text):
    text = re.sub(
        r'\[(hide|spoiler)\](.*?)\[/\1\]',
        r'<div class="spoiler"><button class="toggleButton">展开/隐藏</button><div class="content">\2</div></div>',
        text,
        flags=re.S
    )
    # 清理成对处理后可能残留的孤立 [hide] [/hide] [spoiler] [/spoiler]
    text = re.sub(r'\[/?(?:hide|spoiler)\]', '', text)
    return text

# =========================
# 🧠 bili
# =========================
def process_bili(text):
    def repl(m):
        bv = m.group(2).strip()
        return f'<iframe src="https://player.bilibili.com/player.html?bvid={bv}" width="100%" height="500" allowfullscreen></iframe>'
    return re.sub(r'\[(bili|bilibili)\](.*?)\[/\1\]', repl, text, flags=re.S)

# =========================
# 🧠 media
# =========================
def process_media(text):
    return re.sub(r'\[media\](.*?)\[/media\]',
                  r'<video controls src="\1" style="max-width:100%"></video>',
                  text, flags=re.S)

# =========================
# 🧠 audio
# =========================
def process_audio(text):
    return re.sub(r'\[audio\](.*?)\[/audio\]',
                  r'<audio controls src="\1" style="width:100%"></audio>',
                  text, flags=re.S)

# =========================
# 🧠 url
# =========================
def process_url(text):
    text = re.sub(r'\[url=(.*?)\](.*?)\[/url\]', r'<a href="\1" target="_blank">\2</a>', text, flags=re.S)
    text = re.sub(r'\[url\](.*?)\[/url\]', r'<a href="\1" target="_blank">\1</a>', text, flags=re.S)
    return text

# =========================
# 🧠 img
# =========================
def process_img(text):
    return re.sub(r'\[img\](.*?)\[/img\]',
                  r'<img src="\1" style="max-width:100%">',
                  text, flags=re.S)

# =========================
# 🧠 attach（按扩展名自动识别类型）
# =========================
def process_attach(text):
    # 图片/视频/音频扩展名集
    img_ext = re.compile(r'\.(jpg|jpeg|png|gif|webp|bmp|svg)$', re.I)
    vid_ext = re.compile(r'\.(mp4|webm|ogg|mov|avi|mkv)$', re.I)
    aud_ext = re.compile(r'\.(mp3|wav|flac|aac|ogg|wma)$', re.I)

    def repl(m):
        aid = m.group(1).strip()
        info = ATTACH_MAP.get(aid)

        if info:
            path = info["path"]
            fname = info["filename"]

            # 拼接完整URL，去除ATTACH_BASE路径段在path中重复的前缀
            path_clean = path.lstrip('/')
            base_last = ATTACH_BASE.rstrip('/').rsplit('/', 1)[-1]
            if path_clean.startswith(base_last + '/'):
                path_clean = path_clean[len(base_last) + 1:]
            url = ATTACH_BASE.rstrip('/') + '/' + path_clean

            if img_ext.search(path):
                return f'<img src="{url}" alt="{fname}" style="max-width:100%">'
            if vid_ext.search(path):
                return f'<video controls src="{url}" style="max-width:100%"></video>'
            if aud_ext.search(path):
                return f'<audio controls src="{url}" style="width:100%"></audio>'
            # 其它格式 → 文件下载链接
            return f'<a href="{url}" target="_blank">{fname}</a>'
        else:
            # 没查到映射，兜底
            return f'<a href="{aid}" target="_blank">{aid}</a>'

    return re.sub(r'\[attach(?:img)?\](.*?)\[/attach(?:img)?\]', repl, text, flags=re.S)

# =========================
# 🧠 quote
# =========================
def process_quote(text):
    return re.sub(r'\[quote\](.*?)\[/quote\]',
                  r'<blockquote style="border-left:4px solid #ccc;padding:10px">\1</blockquote>',
                  text, flags=re.S)

# =========================
# 🧠 code
# =========================
def process_code(text):
    return re.sub(r'\[code\](.*?)\[/code\]',
                  r'<pre style="background:#111;color:#0f0;padding:10px;overflow:auto">\1</pre>',
                  text, flags=re.S)

# =========================
# 🧠 basic
# =========================
def process_basic(text):
    text = re.sub(r'\[b\](.*?)\[/b\]', r'<b>\1</b>', text, flags=re.S)
    text = re.sub(r'\[i\](.*?)\[/i\]', r'<i>\1</i>', text, flags=re.S)
    text = re.sub(r'\[u\](.*?)\[/u\]', r'<u>\1</u>', text, flags=re.S)
    text = re.sub(r'\[s\](.*?)\[/s\]', r'<s>\1</s>', text, flags=re.S)
    return text

# =========================
# 🧠 formatting (align/color/size)
# =========================
def process_formatting(text):
    text = re.sub(r'\[align=([^\]]+)\](.*?)\[/align\]', r'<div style="text-align:\1">\2</div>', text, flags=re.S)
    text = re.sub(r'\[color=([^\]]+)\](.*?)\[/color\]', r'<span style="color:\1">\2</span>', text, flags=re.S)
    text = re.sub(r'\[size=([^\]]+)\](.*?)\[/size\]', r'\2', text, flags=re.S)
    return text

# =========================
# 🧠 table
# =========================
def process_table(text):
    def repl_table(m):
        width_attr = m.group(1)
        inner = m.group(2)
        style = f' style="width:{width_attr}"' if width_attr else ''

        inner = re.sub(r'\[tr\](.*?)\[/tr\]', lambda m2: '<tr>' + m2.group(1) + '</tr>', inner, flags=re.S)
        inner = re.sub(r'\[th\](.*?)\[/th\]', r'<th>\1</th>', inner, flags=re.S)
        inner = re.sub(r'\[td\](.*?)\[/td\]', r'<td>\1</td>', inner, flags=re.S)

        return f'<table{style} border="1" cellpadding="5" cellspacing="0">{inner}</table>'

    return re.sub(r'\[table(?:=([^\]]*))?\](.*?)\[/table\]', repl_table, text, flags=re.S)

# =========================
# 🧠 list
# =========================
def process_list(text):
    def repl_list(m):
        list_type = m.group(1)
        inner = m.group(2)

        items = re.split(r'\n?\s*\[\*\]\s*', inner)
        items = [item.strip() for item in items if item.strip()]

        lis = ''.join(f'<li>{item}</li>' for item in items)

        if list_type:
            ol_type = list_type if list_type in ('1','a','A','i','I') else '1'
            return f'<ol type="{ol_type}">{lis}</ol>'
        else:
            return f'<ul>{lis}</ul>'

    return re.sub(r'\[list(?:=([^\]]*))?\](.*?)\[/list\]', repl_list, text, flags=re.S)

# =========================
# 🧠 markdown
# =========================
def process_md(text):
    return re.sub(r'\[md\](.*?)\[/md\]',
                  lambda m: markdown.markdown(m.group(1)),
                  text, flags=re.S)

# =========================
# 🧠 自动<p>
# =========================
def wrap_p(html):
    blocks = ['<img', '<video', '<audio', '<iframe', '<div', '<pre', '<blockquote', '<h',
              '<table', '<ol', '<ul', '<li']

    out = []
    for line in html.split("\n"):
        line = line.strip()
        if not line:
            continue

        if any(line.startswith(b) for b in blocks):
            out.append(line)
        elif line.startswith("<"):
            out.append(line)
        else:
            out.append(f"<p>{line}</p>")

    return "\n".join(out)

# =========================
# 🧠 主解析
# =========================
def parse_content(text):
    if not text:
        return ""

    text = process_spoiler(text)
    text = process_bili(text)
    text = process_media(text)
    text = process_audio(text)

    text = process_attach(text)

    text = process_url(text)
    text = process_img(text)

    text = process_quote(text)
    text = process_code(text)

    text = process_basic(text)
    text = process_formatting(text)
    text = process_table(text)
    text = process_list(text)

    text = process_md(text)

    text = wrap_p(text)

    return text

# =========================
# 🧠 DB
# =========================
def conn_db():
    return pymysql.connect(**DB_CONFIG)

def get_threads(conn):
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""
            SELECT t.tid, t.subject, t.dateline, t.fid,
                   p.message, p.author
            FROM pre_forum_thread t
            JOIN pre_forum_post p ON t.tid=p.tid
            WHERE p.first=1
            ORDER BY t.dateline DESC
        """)
        return cur.fetchall()

def get_replies(conn, tid):
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("""
            SELECT p.message, p.author, p.dateline, p.position
            FROM pre_forum_post p
            WHERE p.tid=%s AND p.first=0
            ORDER BY p.position ASC
        """, (tid,))
        return cur.fetchall()

def get_attach_map(conn):
    """从 pre_forum_attachment_0~9 查询附件映射 aid -> {path, filename}"""
    attach_map = {}
    with conn.cursor() as cur:
        for i in range(10):
            try:
                cur.execute(f"SELECT aid, attachment, filename FROM pre_forum_attachment_{i}")
                for aid, path, fname in cur.fetchall():
                    attach_map[str(aid)] = {"path": path, "filename": fname}
            except pymysql.err.ProgrammingError:
                pass  # 不存在的表跳过
    return attach_map

def get_forum_map(conn):
    """查询 fid -> forum_name 映射"""
    with conn.cursor() as cur:
        cur.execute("SELECT fid, name FROM pre_forum_forum WHERE type IN ('forum', 'sub')")
        return dict(cur.fetchall())

def get_type_map(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT optionid,title FROM pre_forum_typeoption")
        return dict(cur.fetchall())

def get_type_values(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT tid,optionid,value FROM pre_forum_typeoptionvar")
        data = {}
        for tid, opt, val in cur.fetchall():
            data.setdefault(tid, []).append((opt, val))
        return data

# =========================
# 🧠 HTML
# =========================
def build_html(t, type_map, type_values, forum_name="", replies=None, page_footer="", site_name="", favicon_url="", header_html=""):
    tid = t["tid"]
    ts = datetime.fromtimestamp(t["dateline"])
    # 清洗所有从数据库来的字符串
    subject = sanitize(t['subject'])
    author = sanitize(t.get('author', ''))
    forum_name = sanitize(forum_name)
    message = sanitize(t["message"])

    # 站点标题链接（可点击返回首页）
    _icon = f"""<img class="site-icon" src="{favicon_url}" alt=""> """ if favicon_url else ""
    _title = f"{site_name} - 论坛索引" if site_name else "论坛索引"
    site_link = f"""<header class="site-header"><h1 class="site-title"><a href="index.html">{_icon}{_title}</a></h1></header>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
<link rel="stylesheet" href="{SPOILER_CSS}">
<style>
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; color:#222; background:#f5f5f5; line-height:1.7 }}
.container {{ max-width:900px; margin:0 auto; padding:16px }}
.header {{ background:#fff; border-radius:12px; padding:24px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.08) }}
.header h1 {{ font-size:1.4em; margin-bottom:8px; line-height:1.4 }}
.meta {{ font-size:.85em; color:#888 }}
.meta span {{ margin-right:16px }}
.card {{ background:#fff; border-radius:12px; padding:24px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,.08) }}
.card h2 {{ font-size:1.1em; margin-bottom:12px; padding-bottom:8px; border-bottom:2px solid #f0f0f0 }}
.reply {{ border:1px solid #eee; border-radius:10px; padding:14px; margin:10px 0; overflow-wrap:break-word; word-break:break-word }}
.reply-meta {{ font-size:.82em; color:#999; margin-bottom:6px }}
.reply-body {{ border-left:3px solid #e8e8e8; padding-left:12px; overflow-wrap:break-word; word-break:break-word }}
img, video {{ max-width:100%; height:auto; border-radius:6px }}
a {{ color:#1a73e8; text-decoration:none }}
a:hover {{ text-decoration:underline }}
blockquote {{ border-left:4px solid #ddd; padding:10px 14px; margin:10px 0; background:#fafafa; border-radius:4px }}
pre {{ background:#1e1e2e; color:#cdd6f4; padding:14px; overflow-x:auto; border-radius:8px; font-size:.9em }}
table {{ border-collapse:collapse; width:100%; margin:10px 0 }}
th, td {{ border:1px solid #ddd; padding:8px 10px; text-align:left }}
th {{ background:#f8f8f8 }}
.spoiler .toggleButton {{ padding:6px 14px; border:2px solid #ccc; background:#fff; border-radius:6px; cursor:pointer; font-size:.9em }}
.spoiler .content {{ display:none; border:1px solid #ddd; border-radius:6px; padding:12px; margin-top:6px }}
footer.page-footer {{ border-top:1px solid #e0e0e0; margin-top:24px; padding:16px 0; font-size:.85em; color:#999; text-align:center; line-height:1.6 }}
footer.page-footer a {{ color:#1a73e8 }}
.site-title {{ font-size:1.2em; margin-bottom:12px; display:flex; align-items:center; gap:8px }}
.site-title a {{ color:#222; text-decoration:none }}
.site-title a:hover {{ color:#1a73e8 }}
.site-icon {{ height:1em; width:auto; display:block; flex-shrink:0 }}
.site-header {{ margin-bottom:12px }}
.page-header {{ background:#e3f2fd; border:1px solid #90caf9; border-radius:10px; padding:12px 16px; margin-bottom:16px; font-size:.9em; color:#0d47a1; line-height:1.6 }}
.page-header a {{ color:#0d47a1 }}
@media (max-width:600px) {{ .container {{ padding:10px }} .header,.card {{ padding:16px }} .header h1 {{ font-size:1.2em }} }}
</style>
</head>
<body>
<div class="container">
{site_link}
{header_html}
  <div class="header">
    <h1>{subject}</h1>
    <div class="meta">
      <span>✍ {author}</span>
      <span>📅 {ts.strftime('%Y-%m-%d %H:%M')}</span>
      <span>📂 {forum_name}</span>
    </div>
  </div>
"""

    # 分类信息
    if tid in type_values:
        html += '<div class="card"><h2>分类信息</h2><table>'
        for opt, val in type_values[tid]:
            html += f"<tr><td style='width:100px'>{sanitize(type_map.get(opt,'字段'))}</td><td>{sanitize(val)}</td></tr>"
        html += "</table></div>"

    # 正文
    html += '<div class="card"><h2>正文</h2>'
    html += parse_content(message)
    html += "</div>"

    # 回复
    if replies:
        html += '<div class="card"><h2>全部回复</h2>'
        for r in replies:
            html += '<div class="reply">'
            rauthor = sanitize(r.get("author",""))
            rmsg = sanitize(r["message"])
            html += f'<div class="reply-meta"><b>#{sanitize(str(r.get("position","")))}</b> {rauthor} 发表于 {datetime.fromtimestamp(r["dateline"]).strftime("%Y-%m-%d %H:%M")}</div>'
            html += '<div class="reply-body">'
            html += parse_content(rmsg)
            html += '</div></div>'
        html += "</div>"

    page_footer_html = ""
    if page_footer:
        page_footer_html = f"""<footer class="page-footer">{page_footer}</footer>"""

    html += f"""{page_footer_html}
</div>
<script src="{SPOILER_JS}"></script>
</body>
</html>"""

    return html

# =========================
# 🚀 主程序
# =========================
def main():
    global ATTACH_MAP, ATTACH_BASE
    conn = conn_db()

    threads = get_threads(conn)
    type_map = get_type_map(conn)
    type_values = get_type_values(conn)
    forum_map = get_forum_map(conn)

    # 加载附件映射（全局 ATTACH_MAP）
    ATTACH_MAP = get_attach_map(conn)
    print(f"已加载 {len(ATTACH_MAP)} 个附件映射")

    include_replies = input("是否包含回复？(Y/n)：").strip().lower() != 'n'

    exclude_input = input("要排除的帖子ID（多个用半角逗号分隔，直接回车不排除）：").strip()
    exclude_ids = set()
    if exclude_input:
        for tid in exclude_input.split(','):
            tid = tid.strip()
            if tid.isdigit():
                exclude_ids.add(int(tid))
    if exclude_ids:
        print(f"已排除 {len(exclude_ids)} 个帖子: {sorted(exclude_ids)}")

    # ---- 输入公告 ----
    announcement = input("首页公告文字（支持使用HTML代码，直接回车不展示公告区域）：").strip()

    # ---- 输入页头 ----
    page_header = input("页头内容（支持HTML，直接回车不展示）：").strip()

    # ---- 输入页脚 ----
    page_footer = input("页脚内容（支持HTML，直接回车不展示）：").strip()

    # ---- 输入每页数量 ----
    per_page_input = input("首页每页显示的帖子数量（直接回车默认 20）：").strip()
    per_page = 20
    if per_page_input.isdigit() and int(per_page_input) > 0:
        per_page = int(per_page_input)

    # ---- 输入站点名称 ----
    site_name = input("站点名称（用于页面标题，直接回车仅显示\"论坛索引\"）：").strip()

    # ---- 输入图标链接 ----
    favicon_url = input("图标链接（用于favicon和页面左上角图标，直接回车不展示图标）：").strip()

    # ---- 输入附件CDN地址 ----
    while True:
        cdn_input = input("附件CDN地址（必填，例如 https://cdn.example.com）：").strip()
        if cdn_input:
            ATTACH_BASE = cdn_input.rstrip('/')
            break
        print("附件CDN地址不能为空，请重新输入。")

    # ---- 提前生成公告 / 页头 / 页脚 HTML ----
    announce_html = f"""<div class="announcement">{announcement}</div>""" if announcement else ""
    header_html = f"""<header class="page-header">{page_header}</header>""" if page_header else ""
    footer_html = f"""<footer class="page-footer">{page_footer}</footer>""" if page_footer else ""

    # 收集有效帖子（排除后）
    valid_threads = []
    for t in threads:
        if t["tid"] in exclude_ids:
            continue

        forum_name = forum_map.get(t.get("fid"), "")
        replies = get_replies(conn, t["tid"]) if include_replies else []
        html = build_html(t, type_map, type_values, forum_name, replies, page_footer, site_name, favicon_url, header_html)

        name = f"thread-{t['tid']}-1-1.html"
        with open(os.path.join(export_dir, name), "w", encoding="utf-8") as f:
            f.write(html)

        valid_threads.append({**t, "forum_name": forum_name, "file": name})
        print("导出:", name)

    # ---- 生成 data.json ----
    json_data = []
    for vt in valid_threads:
        json_data.append({
            "tid": vt["tid"],
            "subject": sanitize(vt["subject"]),
            "author": sanitize(vt.get("author", "")),
            "dateline": vt["dateline"],
            "forum": sanitize(vt["forum_name"]),
            "file": vt["file"]
        })
    import json
    with open(os.path.join(export_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    # ---- 生成 index.html ----
    cards_html = ""
    for vt in valid_threads:
        ts = datetime.fromtimestamp(vt["dateline"])
        subj = sanitize(vt['subject'])
        auth = sanitize(vt.get('author', ''))
        fname = sanitize(vt['forum_name'])
        ffile = vt['file']
        cards_html += f"""<a href="{ffile}" class="card">
  <div class="card-title">{subj}</div>
  <div class="card-meta">
    <span>✍ {auth}</span>
    <span>📅 {ts.strftime('%Y-%m-%d %H:%M')}</span>
    <span>📂 {fname}</span>
  </div>
</a>"""

    # ---- 站点名称/图标相关 ----
    page_title = f"{site_name} - 论坛索引" if site_name else "论坛索引"
    favicon_html = f"""<link rel="icon" href="{favicon_url}">""" if favicon_url else ""
    icon_img = f"""<img class="site-icon" src="{favicon_url}" alt=""> """ if favicon_url else ""

    index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{favicon_html}
<title>{page_title}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0 }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; color:#222; background:#f5f5f5; line-height:1.5 }}
.container {{ max-width:800px; margin:0 auto; padding:16px }}
h1 {{ font-size:1.5em; margin-bottom:16px; display:flex; align-items:center; gap:8px }}
.site-icon {{ height:1em; width:auto; display:block; flex-shrink:0 }}
.site-header {{ margin-bottom:12px }}
.toolbar {{ display:flex; gap:8px; margin-bottom:16px }}
.toolbar .search-box {{ flex:1; min-width:0; padding:12px 16px; border:2px solid #ddd; border-radius:10px; font-size:1em; outline:none; transition:border-color .2s; background:#fff }}
.toolbar .search-box:focus {{ border-color:#1a73e8 }}
.sort-select {{ padding:12px 14px; border:2px solid #ddd; border-radius:10px; font-size:.9em; outline:none; background:#fff; cursor:pointer; white-space:nowrap }}
.sort-select:focus {{ border-color:#1a73e8 }}
.announcement {{ background:#fff8e1; border:1px solid #ffe082; border-radius:10px; padding:12px 16px; margin-bottom:16px; font-size:.9em; color:#6d4c00; line-height:1.6 }}
.announcement a {{ color:#e65100 }}
header.page-header {{ background:#e3f2fd; border:1px solid #90caf9; border-radius:10px; padding:12px 16px; margin-bottom:16px; font-size:.9em; color:#0d47a1; line-height:1.6 }}
header.page-header a {{ color:#0d47a1 }}
footer.page-footer {{ border-top:1px solid #e0e0e0; margin-top:24px; padding:16px 0; font-size:.85em; color:#999; text-align:center; line-height:1.6 }}
footer.page-footer a {{ color:#1a73e8 }}
.card {{ display:block; background:#fff; border-radius:12px; padding:16px 20px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,.06); text-decoration:none; transition:box-shadow .2s,transform .15s }}
.card:hover {{ box-shadow:0 4px 12px rgba(0,0,0,.12); transform:translateY(-1px) }}
.card-title {{ font-size:1em; color:#1a73e8; font-weight:600; margin-bottom:6px; line-height:1.4 }}
.card-meta {{ font-size:.8em; color:#999 }}
.card-meta span {{ margin-right:12px }}
.hidden {{ display:none !important }}
.pagination {{ display:flex; flex-wrap:wrap; justify-content:center; gap:6px; margin-top:20px; margin-bottom:10px }}
.page-btn {{ padding:6px 14px; border:2px solid #ddd; border-radius:8px; background:#fff; cursor:pointer; font-size:.85em; transition:all .15s }}
.page-btn:hover {{ border-color:#1a73e8; color:#1a73e8 }}
.page-btn.active {{ background:#1a73e8; border-color:#1a73e8; color:#fff }}
@media (max-width:600px) {{ .container {{ padding:10px }} .card {{ padding:14px 16px }} }}
</style>
</head>
<body>
<div class="container">
<header class="site-header"><h1>{icon_img}{page_title}</h1></header>
<div class="toolbar">
  <input type="text" class="search-box" id="search" placeholder="搜索帖子标题、作者、版块..." autofocus>
  <select class="sort-select" id="sort">
    <option value="desc">从新到旧</option>
    <option value="asc">从旧到新</option>
  </select>
</div>
{announce_html}
{header_html}
<div id="list">{cards_html}</div>
<div class="pagination" id="pagination"></div>
{footer_html}
</div>
<script>
(function(){{
var data={json.dumps(json_data, ensure_ascii=False)};
var pageSize={per_page};
var list=document.getElementById('list');
var search=document.getElementById('search');
var pagination=document.getElementById('pagination');
var cards=Array.from(list.getElementsByClassName('card'));
var totalPages=Math.ceil(cards.length/pageSize)||1;

function getPage(){{
  var m=location.search.match(/[?&]page=(\\d+)/);
  var p=m?parseInt(m[1],10):1;
  return Math.max(1,Math.min(p,totalPages));
}}

function showPage(p){{
  for(var i=0;i<cards.length;i++){{
    cards[i].classList.toggle('hidden',i<(p-1)*pageSize||i>=p*pageSize);
  }}
  var btns=pagination.querySelectorAll('.page-btn');
  for(var i=0;i<btns.length;i++){{
    btns[i].classList.toggle('active',parseInt(btns[i].dataset.page)===p);
  }}
  var url=new URL(location);
  url.searchParams.set('page',p);
  history.replaceState(null,'',url);
}}

function renderPagination(){{
  pagination.innerHTML='';
  for(var p=1;p<=totalPages;p++){{
    var btn=document.createElement('button');
    btn.className='page-btn';
    btn.textContent=p;
    btn.dataset.page=p;
    btn.addEventListener('click',(function(page){{return function(){{showPage(page);search.value='';}};}})(p));
    pagination.appendChild(btn);
  }}
}}

search.addEventListener('input',function(){{
  var q=this.value.trim().toLowerCase();
  var hasQuery=!!q;
  pagination.style.display=hasQuery?'none':'flex';
  for(var i=0;i<cards.length;i++){{
    var info=data[i];
    var match=!hasQuery||info.subject.toLowerCase().includes(q)||info.author.toLowerCase().includes(q)||info.forum.toLowerCase().includes(q);
    cards[i].classList.toggle('hidden',!match);
  }}
  if(!hasQuery) showPage(getPage());
}});

function formatDate(ts){{
  var d=new Date(ts*1000);
  function pad(n){{return n<10?'0'+n:n}}
  return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '+pad(d.getHours())+':'+pad(d.getMinutes());
}}

function renderCards(arr){{
  list.innerHTML='';
  for(var i=0;i<arr.length;i++){{
    var d=arr[i];
    var a=document.createElement('a');
    a.className='card';
    a.href=d.file;
    a.innerHTML='<div class="card-title">'+d.subject+'</div><div class="card-meta"><span>✍ '+d.author+'</span><span>📅 '+formatDate(d.dateline)+'</span><span>📂 '+d.forum+'</span></div>';
    list.appendChild(a);
  }}
  cards=Array.from(list.getElementsByClassName('card'));
  totalPages=Math.ceil(cards.length/pageSize)||1;
}}

var sortSelect=document.getElementById('sort');
sortSelect.addEventListener('change',function(){{
  var order=this.value;
  data.sort(function(a,b){{return order==='asc'?a.dateline-b.dateline:b.dateline-a.dateline}});
  renderCards(data);
  renderPagination();
  pagination.style.display='flex';
  search.value='';
  showPage(1);
}});

renderCards(data);
renderPagination();
showPage(getPage());
}})();
</script>
</body>
</html>"""

    with open(os.path.join(export_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    conn.close()
    print(f"完成 🎉 输出: {export_dir} | 共 {len(valid_threads)} 个帖子")

if __name__ == "__main__":
    main()
