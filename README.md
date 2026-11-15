# twitter-archive-recovery

Recover and archive a **deleted X (Twitter) account** end-to-end: discover Wayback Machine captures, download all archived tweet JSONs despite aggressive rate limiting, salvage media images through a three-tier pipeline, and produce a portable self-contained HTML timeline.

No API keys required. Works entirely with public endpoints (Wayback CDX / if_ views, `pbs.twimg.com`).

## Pipeline

```
discover.py ──> targets.json ──> fetch.py ──> wb/*.json ──> recover_media.py ──> img/ ──> build_standalone.py ──> account.html
  (CDX 枚举)      (窗口骑手下载)      (三层级媒体抢救)          (单文件自包含主页)
```

## Usage

```bash
# 1. Enumerate all Wayback captures for a username
python tools/discover.py <username> targets.json [proxy]

# 2. Download tweet JSONs (window-rider pacing, resumable)
python tools/fetch.py <username> targets.json wb [proxy] [clash_api] [clash_secret]

# 3. Recover media (pbs plain URL -> Wayback CDX fallback)
python tools/recover_media.py wb img [proxy]

# 4. Build the standalone HTML
python tools/build_standalone.py wb img account.html <username> [avatar.jpg] [banner.jpg]
```

`proxy` = `http://host:port` or `-` for none. Clash API rotation (optional) is used when consecutive 429s occur; pre-probe node health before enabling.

## Why this exists

Recovering a deleted account fights several non-obvious enemies:

| Problem | Reality discovered in the field |
|---|---|
| Wayback 429s | The `id_` raw endpoint is a bot-target and flaps heavily. The **`if_` view is served far more freely** — the tweet JSON is inside a `<pre>` tag. |
| Pacing | 429s come in **windows**: open 1-3 min, closed 1-5 min. Constant hammering prolongs closures. Use quick-probe pacing + sweep rounds, never parallel downloaders on one exit IP. |
| Media "404"s | After deactivation, `?format=jpg&name=large` params 404 while the **plain URL still works**. Worse: **blocked exit IPs receive fake 404s** for images that are alive on clean IPs. Always re-test with a clean network (cloud sandbox / home broadband) before declaring an image lost. |
| CDX gaps | Single CDX pulls can silently miss captures (server-side pagination/flakiness). Re-pull after a few hours and merge. |
| LLM-provided URLs | LLM assistants recall **status IDs reliably but image filenames only ~30% correctly**. Prefer asking for status links; verify image candidates directly. |
| OOM | Headed browsers get OOM-killed on long jobs. Use headless; resumable file-per-tweet layout means a crash costs nothing. |

## Key techniques

- **Snowflake decoding** of tweet IDs gives exact post timestamps: `(id >> 22) + 1288834974657` ms.
- **CDX time-window scans** (`from`/`to`) around a known post time can locate media captures for unarchived tweets.
- **Three-tier media recovery**: pbs plain URL (fast, unlimited) → per-image Wayback CDX prefix lookup → clean-IP retry channel (e.g. an AI assistant's code sandbox, which has clean egress).
- **Node rotation via Clash API** (`PUT /proxies/GLOBAL`) after N consecutive 429/502/503s — but health-probe nodes first; shared-airport nodes are often dead.
- **Standalone HTML**: images inlined as base64; the avatar (repeated on every card) is injected once via JS to avoid file bloat.

## Prior art

Related projects handle the basic Wayback-text path: [BackXive](https://github.com/zozonteq/backxive), [twayback](https://github.com/humandecoded/twayback), [tweetext](https://github.com/clopso/tweetext), [Tweet-Machine](https://github.com/0xcyberpj/tweet-machine), [tweetfisher](https://github.com/kulgg/tweetfisher). None cover the media-recovery layers, fake-404 detection, or rate-limit window tactics documented above.

## Legal

Use only for accounts you own, with the account owner's consent, or for legitimate OSINT/archival research within applicable law and platform terms.
