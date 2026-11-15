# -*- coding: utf-8 -*-
"""
窗口骑手式推文下载器: 从 Wayback Machine if_ 视图恢复已删除账号的推文 JSON。
用法: python fetch.py <username> <targets.json> <out_dir> [proxy] [clash_api] [clash_secret]
targets.json: [[capture_ts, original_url], ...]  (由 discover.py 生成)
断点续传: 已存在的 {ts}_{id}.json 自动跳过。
"""
import json, os, sys, io, time, re, random, urllib.request, urllib.error, html as H

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

def main():
    username = sys.argv[1]
    targets = json.load(open(sys.argv[2], encoding="utf-8"))
    outdir = sys.argv[3]
    proxy = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    clash_api = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] != "-" else None
    clash_secret = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] != "-" else None

    os.makedirs(outdir, exist_ok=True)
    handlers = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    opener = urllib.request.build_opener(*handlers)

    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    node_idx = [0]
    NODES = None  # 如需轮换, 在下方填入你的节点名列表

    def rotate():
        if not (clash_api and clash_secret and NODES):
            log("rotate: no nodes configured, waiting 60s")
            time.sleep(60)
            return
        node = NODES[node_idx[0] % len(NODES)]
        node_idx[0] += 1
        try:
            req = urllib.request.Request(f"{clash_api}/proxies/GLOBAL",
                data=json.dumps({"name": node}).encode(), method="PUT")
            req.add_header("Authorization", f"Bearer {clash_secret}")
            req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(req, timeout=10).read()
            log(f"rotate -> {node}")
        except Exception as e:
            log(f"rotate fail: {e}")
        time.sleep(8)

    def fetch_one(ts, orig):
        """返回 bytes=成功; ("http",code)=HTTP错误; ("err",msg)=其他; None=页面无JSON"""
        url = f"https://web.archive.org/web/{ts}if_/{orig}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            html = opener.open(req, timeout=20).read().decode("utf-8", errors="replace")
            m = re.search(r'<pre[^>]*>(.*?)</pre>', html, re.S)
            if m:
                raw = m.group(1).strip()
                try:
                    d = json.loads(raw)
                except Exception:
                    d = json.loads(H.unescape(raw))
                if "data" in d and "text" in d.get("data", {}):
                    return json.dumps(d, ensure_ascii=False).encode("utf-8")
            try:
                d = json.loads(html)
                if "data" in d and "text" in d.get("data", {}):
                    return html.encode("utf-8")
            except Exception:
                pass
            return None
        except urllib.error.HTTPError as e:
            return ("http", e.code)
        except Exception as e:
            return ("err", str(e)[:60])

    log(f"start: {len(targets)} targets, username={username}")
    ok = cons = 0
    for i, (ts, orig) in enumerate(targets):
        sid = orig.split("/")[-1]
        fn = os.path.join(outdir, f"{ts}_{sid}.json")
        if os.path.exists(fn) and os.path.getsize(fn) > 200:
            continue
        r = fetch_one(ts, orig)
        if isinstance(r, bytes):
            with open(fn, "wb") as f:
                f.write(r)
            ok += 1
            cons = 0
        elif r and r[0] == "http" and r[1] in (429, 502, 503):
            cons += 1
            if cons >= 8:
                rotate()
                cons = 0
        else:
            log(f"fail {sid}: {r}")
        if (i + 1) % 20 == 0:
            log(f"progress {i+1}/{len(targets)} ok={ok}")
        time.sleep(random.uniform(2, 3.2))

    # 补漏轮
    for roundn in range(6):
        missing = [(ts, u) for ts, u in targets
                   if not (os.path.exists(os.path.join(outdir, f"{ts}_{u.split('/')[-1]}.json"))
                           and os.path.getsize(os.path.join(outdir, f"{ts}_{u.split('/')[-1]}.json")) > 200)]
        if not missing:
            break
        log(f"sweep round {roundn+1}: {len(missing)} missing")
        for ts, u in missing:
            sid = u.split("/")[-1]
            fn = os.path.join(outdir, f"{ts}_{sid}.json")
            r = fetch_one(ts, u)
            if isinstance(r, bytes):
                with open(fn, "wb") as f:
                    f.write(r)
                ok += 1
                cons = 0
            elif r and r[0] == "http" and r[1] in (429, 502, 503):
                cons += 1
                if cons >= 8:
                    rotate()
                    cons = 0
            time.sleep(random.uniform(2, 3.2))
    remain = sum(1 for ts, u in targets
                 if not (os.path.exists(os.path.join(outdir, f"{ts}_{u.split('/')[-1]}.json"))
                         and os.path.getsize(os.path.join(outdir, f"{ts}_{u.split('/')[-1]}.json")) > 200))
    log(f"DONE ok={ok} remain={remain}")

if __name__ == "__main__":
    main()
