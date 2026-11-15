# -*- coding: utf-8 -*-
"""
CDX 存档发现: 枚举目标账号的全部 Wayback 捕获,输出 fetch.py 可用的 targets.json。
用法: python discover.py <username> <out_targets.json> [proxy]
注意: 多次运行(间隔数小时)可发现新入库的捕获,合并去重即可。
"""
import json, sys, io, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0"

def main():
    username = sys.argv[1]
    out = sys.argv[2]
    proxy = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    opener = urllib.request.build_opener(*handlers)

    rows = []
    for domain in (f"twitter.com/{username}", f"x.com/{username}", f"mobile.twitter.com/{username}"):
        url = ("http://web.archive.org/cdx/search/cdx?url=" + urllib.parse.quote(domain + "*")
               + "&output=json&fl=timestamp,original,statuscode,mimetype,digest,length&collapse=urlkey")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            data = json.loads(opener.open(req, timeout=90).read().decode("utf-8", errors="replace"))
            n = len(data) - 1 if data else 0
            print(f"{domain}: {n} captures")
            rows.extend(data[1:] if data else [])
        except Exception as e:
            print(f"{domain}: FAIL {e}")

    # 合并去重(按 original URL),仅保留 status 页面
    seen, targets = {}, []
    for r in rows:
        orig = r[1]
        if "/status/" not in orig:
            continue
        if orig not in seen or r[0] > seen[orig]:
            seen[orig] = r[0]
    for orig, ts in seen.items():
        targets.append([ts, orig])
    targets.sort(key=lambda x: x[0], reverse=True)
    json.dump(targets, open(out, "w"))
    print(f"total unique status captures: {len(targets)} -> {out}")

if __name__ == "__main__":
    main()
