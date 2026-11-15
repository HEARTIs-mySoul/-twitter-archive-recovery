# -*- coding: utf-8 -*-
"""
三层级媒体抢救:
1. pbs 原始 URL(无格式参数)直下 —— 最快通道
2. Wayback CDX 前缀查档 + id_ 温和下载 —— 兜底
3. 对 404 的图,提示用干净 IP 沙盒复测(404 可能是出口 IP 被拉黑,不是图被删)
用法: python recover_media.py <json_dir> <img_dir> [proxy]
"""
import json, os, sys, io, time, glob, random, urllib.request, urllib.error, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0"

def main():
    jsondir, imgdir = sys.argv[1], sys.argv[2]
    proxy = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    opener = urllib.request.build_opener(*handlers)
    os.makedirs(imgdir, exist_ok=True)

    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    def pbs_fetch(base):
        # 关键: 无参数 URL 优先! 注销账号的 ?format=... 参数会 404
        for url in (base, f"{base}?format=jpg&name=orig"):
            for _ in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": UA})
                    data = opener.open(req, timeout=40).read()
                    if len(data) > 500:
                        return data
                except Exception:
                    time.sleep(3)
        return None

    def wb_fetch(base):
        cdx = ("http://web.archive.org/cdx/search/cdx?url=" + urllib.parse.quote(base)
               + "&matchType=prefix&output=json&limit=20&filter=statuscode:200")
        try:
            req = urllib.request.Request(cdx, headers={"User-Agent": UA})
            rows = json.loads(opener.open(req, timeout=30).read().decode("utf-8", errors="replace"))
        except Exception:
            return None
        if not rows or len(rows) < 2:
            return None
        imgs = [r for r in rows[1:] if (r[3] or "").startswith("image/")]
        if not imgs:
            return None
        imgs.sort(key=lambda r: int(r[6]) if str(r[6]).isdigit() else 0, reverse=True)
        ts, orig = imgs[0][1], imgs[0][2]
        for attempt in range(3):
            try:
                req = urllib.request.Request(f"http://web.archive.org/web/{ts}id_/{orig}",
                                             headers={"User-Agent": UA})
                data = opener.open(req, timeout=40).read()
                if len(data) > 500:
                    return data
            except urllib.error.HTTPError:
                time.sleep(random.uniform(30, 50))  # 温和等窗口
            except Exception:
                time.sleep(10)
        return None

    urls = set()
    for fn in glob.glob(os.path.join(jsondir, "*.json")):
        try:
            d = json.load(open(fn, encoding="utf-8"))
        except Exception:
            continue
        for m in d.get("includes", {}).get("media", []):
            if m.get("url"):
                urls.add(m["url"].split("?")[0])

    log(f"unique media: {len(urls)}")
    ok = pbs_ok = wb_ok = miss = 0
    clean_ip_hint = []
    for base in sorted(urls):
        name = os.path.basename(base)
        out = os.path.join(imgdir, "media_" + name)
        if os.path.exists(out) and os.path.getsize(out) > 500:
            continue
        data = pbs_fetch(base)
        if data:
            open(out, "wb").write(data)
            ok += 1; pbs_ok += 1
            log(f"pbs ok {name}")
            time.sleep(random.uniform(0.5, 1.0))
            continue
        data = wb_fetch(base)
        if data:
            open(out, "wb").write(data)
            ok += 1; wb_ok += 1
            log(f"wayback ok {name}")
        else:
            miss += 1
            clean_ip_hint.append(base)
            log(f"MISS {name} (pbs404 + 无档; 记得用干净IP沙盒复测!)")
        time.sleep(random.uniform(2, 3.5))

    log(f"DONE ok={ok} (pbs={pbs_ok}, wayback={wb_ok}) miss={miss}")
    if clean_ip_hint:
        with open(os.path.join(imgdir, "..", "clean_ip_retry.txt"), "w") as f:
            f.write("\n".join(clean_ip_hint))
        log("疑似假404清单已存 clean_ip_retry.txt —— 用干净网络(云沙盒/家用宽带)复测这些URL")

if __name__ == "__main__":
    main()
