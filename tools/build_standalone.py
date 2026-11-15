# -*- coding: utf-8 -*-
"""
从推文 JSON 生成单文件自包含 HTML 主页(仿 X 深色风格)。
用法: python build_standalone.py <json_dir> <img_dir> <out.html> <username> [avatar_jpg] [banner_jpg]
图片全部 base64 内嵌; 重复出现的头像用 JS 注入一份(否则体积爆炸)。
缺图自动显示占位符, 补图后重跑即可增量更新。
"""
import json, os, sys, io, glob, base64, re, html as H
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}

def main():
    jsondir, imgdir, out_html, username = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    avatar = sys.argv[5] if len(sys.argv) > 5 and os.path.exists(sys.argv[5]) else None
    banner = sys.argv[6] if len(sys.argv) > 6 and os.path.exists(sys.argv[6]) else None

    tweets, media_of, user = {}, {}, None
    for fn in glob.glob(os.path.join(jsondir, "*.json")):
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except Exception:
            continue
        data = d.get("data")
        if not data or "text" not in data:
            continue
        tweets[data["id"]] = data
        media_of[data["id"]] = d.get("includes", {}).get("media", [])
        for u in d.get("includes", {}).get("users", []):
            if u.get("username") == username:
                user = u

    order = sorted(tweets.values(), key=lambda t: int(t["id"]), reverse=True)
    name = (user or {}).get("name", username)
    desc = (user or {}).get("description", "")
    pm = (user or {}).get("public_metrics", {}) or {}

    def esc(s):
        return H.escape(s or "", quote=False)

    def fmt(iso):
        try:
            t = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8)))
            return f"{t.year}年{t.month}月{t.day}日 {t.hour:02d}:{t.minute:02d}"
        except Exception:
            return iso

    def img_path(name):
        return os.path.join(imgdir, name)

    def media_cells(data):
        imgs = media_of.get(data["id"], [])
        cells, files = [], []
        for m in imgs:
            u = (m.get("url") or "").split("?")[0]
            fn = "media_" + os.path.basename(u)
            if os.path.exists(img_path(fn)) and os.path.getsize(img_path(fn)) > 500:
                cells.append(f'<img loading="lazy" data-b64="1" data-f="{fn}" alt="">')
                files.append(fn)
            else:
                cells.append('<div class="miss">图片未恢复</div>')
        cls = {1: "c1", 2: "c2", 3: "c3", 4: "c4"}.get(len(cells), "c4")
        return f'<div class="imgs {cls}">{"".join(cells)}</div>' if cells else "", files

    cards, allfiles, n_miss = [], set(), 0
    for t in order:
        text = t.get("text", "")
        ref = t.get("referenced_tweets") or []
        badge = "转推" if any(r.get("type") == "retweeted" for r in ref) else ""
        pm_t = t.get("public_metrics") or {}
        imgs_html, files = media_cells(t)
        allfiles.update(files)
        badge_html = f'<span class="badge">{badge}</span>' if badge else ""
        cards.append(
            f'<div class="tweet"><img class="av" data-av="1" alt="">'
            f'<div class="body"><div class="head"><span class="n">{esc(name)}</span>'
            f'<span class="h"> @{esc(username)}</span>{badge_html}'
            f'<span class="d"> · {esc(fmt(t.get("created_at", "")))}</span></div>'
            f'<div class="text">{esc(text)}</div>{imgs_html}'
            f'<div class="foot"><span>💬 {pm_t.get("reply_count", 0)}</span>'
            f'<span>❤️ {pm_t.get("like_count", 0)}</span></div></div></div>'
        )

    # base64 映射(每张图一份,JS 注入)
    b64map = {}
    for fn in sorted(allfiles):
        ext = os.path.splitext(fn)[1].lower()
        b64map[fn] = f"data:{MIME.get(ext, 'image/jpeg')};base64," + \
                     base64.b64encode(open(img_path(fn), "rb").read()).decode()
    av_b64 = base64.b64encode(open(avatar, "rb").read()).decode() if avatar else ""
    ban_b64 = base64.b64encode(open(banner, "rb").read()).decode() if banner else ""
    cover = f'background-image:url(\'data:image/jpeg;base64,{ban_b64}\')' if ban_b64 else \
            'background-image:linear-gradient(135deg,#1d9bf0,#794bc4,#ff2e6e)'

    bio = esc(desc).replace("\n", "<br>")
    page = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(name)} (@{esc(username)}) · 存档还原</title>
<style>
*{{box-sizing:border-box}} body{{background:#000;color:#e7e9ea;margin:0;font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}}
.page{{max-width:640px;margin:0 auto;min-height:100vh;border-left:1px solid #2f3336;border-right:1px solid #2f3336}}
.notice{{padding:12px 16px;background:#16181c;border-bottom:1px solid #2f3336;font-size:13px;color:#71767b;line-height:1.5}}
.cover{{height:140px;{cover};background-size:cover;background-position:center}}
.avatar{{width:124px;height:124px;border-radius:50%;border:4px solid #000;margin:-64px 16px 0;object-fit:cover;background:#333}}
.profile{{padding:4px 16px 16px}}.name{{font-size:20px;font-weight:800}}.handle{{color:#71767b;font-size:15px}}
.bio{{margin-top:12px;font-size:15px;line-height:1.45;white-space:pre-wrap}}
.stats{{display:flex;gap:20px;margin-top:12px;font-size:14px;color:#71767b}}.stats b{{color:#e7e9ea}}
.tabs{{display:flex;border-bottom:1px solid #2f3336;font-size:15px;font-weight:700;position:sticky;top:0;background:rgba(0,0,0,.9)}}
.tab{{padding:15px 16px;color:#71767b;cursor:pointer}}.tab.active{{color:#e7e9ea;border-bottom:4px solid #1d9bf0}}
.panel{{display:none}}.panel.active{{display:block}}
.tweet{{display:flex;padding:12px 16px;border-bottom:1px solid #2f3336;gap:10px}}
.tweet .av{{width:40px;height:40px;border-radius:50%;flex-shrink:0;object-fit:cover;background:#333}}
.tweet .body{{flex:1;min-width:0}}.head .n{{font-weight:700}}.head .h,.head .d{{color:#71767b;font-size:14px}}
.badge{{color:#71767b;font-size:13px;margin-left:6px}}.tweet .text{{font-size:15px;margin-top:3px;white-space:pre-wrap;word-wrap:break-word;line-height:1.45}}
.imgs{{display:grid;gap:2px;margin-top:10px;border-radius:16px;overflow:hidden;border:1px solid #2f3336}}
.imgs.c1{{grid-template-columns:1fr}}.imgs.c2{{grid-template-columns:1fr 1fr}}.imgs.c3{{grid-template-columns:1fr 1fr 1fr}}.imgs.c4{{grid-template-columns:1fr 1fr}}
.imgs img{{width:100%;height:100%;object-fit:cover;max-height:510px;min-height:120px;display:block}}
.imgs .miss{{display:flex;align-items:center;justify-content:center;color:#71767b;font-size:13px;background:#16181c;min-height:120px}}
.tweet .foot{{color:#71767b;font-size:13px;margin-top:8px;display:flex;gap:28px}}
</style></head><body><div class="page">
<div class="notice">⚠️ 离线存档还原 · 数据来自 Wayback Machine 对 @{esc(username)} 的捕获 · 仅供个人存档</div>
<div class="cover"></div>
<img class="avatar" data-av="1" alt="avatar">
<div class="profile"><div class="name">{esc(name)}</div><div class="handle">@{esc(username)}</div>
<div class="bio">{bio}</div>
<div class="stats"><span><b>{pm.get("followers_count", "?")}</b> 关注者</span><span><b>{pm.get("following_count", "?")}</b> 关注中</span><span><b>{len(order)}</b> 条已恢复推文</span></div></div>
<div class="tabs"><div class="tab active" data-p="p1">推文 ({len(order)})</div></div>
<div class="panel active" id="p1">{''.join(cards)}</div>
</div>
<script>
var B64={json.dumps(b64map, ensure_ascii=False)};
var AV='data:image/jpeg;base64,{av_b64}';
document.querySelectorAll('img[data-av]').forEach(function(e){{e.src=AV;}});
document.querySelectorAll('img[data-b64]').forEach(function(e){{var u=B64[e.dataset.f];if(u){{e.src=u;}}}});
document.querySelectorAll('.tab').forEach(function(t){{t.addEventListener('click',function(){{document.querySelectorAll('.tab').forEach(function(x){{x.classList.remove('active')}});document.querySelectorAll('.panel').forEach(function(x){{x.classList.remove('active')}});t.classList.add('active');document.getElementById(t.dataset.p).classList.add('active');}});}});
</script>
</body></html>"""
    open(out_html, "w", encoding="utf-8").write(page)
    print(f"OK: {out_html} ({len(order)} tweets, {len(b64map)} images, {os.path.getsize(out_html)/1024/1024:.1f} MB)")

if __name__ == "__main__":
    main()
