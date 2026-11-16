---
title: DNS, delivery, caching, and latency · Lab
summary: Watch ETag revalidation and Cache API hits locally, run the anycast request-path labs in lab.net, dry-run the cache rules, and inspect DNS and cf-ray on a deployed shop.
---

## Before you start

Start the shop ([deploy lab](/labs/deploy/), step 2) on port 8788, and the Academy Worker in a second terminal:

```bash
npm run dev --prefix academy
```

```output
Academy: 39 pages, 44 repo embeds, 0 real and 8 simulated datasets on pages.
⛅️ wrangler 4.162.0
Your Worker has access to the following bindings:
env.LAB_LIMITER (20 requests/60 seconds)      Rate Limit                    local
env.LAB_EVENTS (academy_lab)                  Analytics Engine Dataset      local
env.ASSETS                                    Assets                        local
env.DEPLOYMENT ("local")                      Environment Variable          local
[wrangler:info] Ready on http://localhost:8787
```

Page and embed counts change as the Academy grows.

## 1. Static pages revalidate with ETags

```bash
curl -sI http://127.0.0.1:8788/llms.txt | grep -i -E 'cache-control|etag'
ETAG=$(curl -sI http://127.0.0.1:8788/llms.txt | awk -F': ' 'tolower($1)=="etag"{print $2}' | tr -d '\r')
curl -s -o /dev/null -w '%{http_code}\n' -H "If-None-Match: $ETAG" http://127.0.0.1:8788/llms.txt
```

```output
Cache-Control: public, max-age=0, must-revalidate
ETag: "638d59d498cd1d1c35a8685f74b3341f"
304
```

The browser may keep the file but must ask first. The answer is a 304 with no body. Your ETag value will differ.

## 2. The Cache API in a Function

```bash
for i in 1 2 3; do curl -s -o /dev/null -D - http://127.0.0.1:8788/api/stock | grep -i server-timing; done
```

```output
Server-Timing: cache;desc="MISS";dur=1, kv;desc="STOCK get";dur=2
Server-Timing: cache;desc="HIT";dur=1
Server-Timing: cache;desc="HIT";dur=0
```

If the first line already says HIT, an earlier request within 30 seconds filled the cache. Wait 30 seconds and try again.

## 3. The Cache API in the Academy Worker

```bash
curl -s -D - "http://localhost:8787/api/lab/cache?key=demo&ttl=30" -o /dev/null | grep -i -E 'x-academy-cache|cache-control'
curl -s -D - "http://localhost:8787/api/lab/cache?key=demo&ttl=30" -o /dev/null | grep -i -E 'x-academy-cache|age'
```

```output
Cache-Control: public, max-age=30
X-Academy-Cache: MISS
X-Academy-Cache: HIT
```

::: live cache

## 4. Run the anycast lab in lab.net (browser)

The request-path labs use [lab.net](/reference/labnet/). The quickest way in is the browser build at exergy-connect.com: the **Open this lab in lab.net** button under each figure on the [Explore page](/explore/delivery/) carries the topology file inside the link (lab.net's `#lab=` gzip artefact), so nothing is uploaded anywhere.

1. Open the lab and press **Launch**. BGP sessions come up between the ISP, transit, and both edge routers.
2. Press **Validate**. All three checks pass: the ISP prefers the direct IAH peering, and the visitor's ping is answered by `web_iah`.
3. Right-click the `isp_hou`–`cf_iah` link and disable it. BGP reconverges over transit.
4. Validate again. The route and ping checks now fail because this file expects IAH, and the ping detail reports the reply from `web_dfw`. That is anycast failover. [anycast-edge-failover.xp](repo:network/labnet/anycast-edge-failover.xp) encodes the post-failure expectations.

## 5. Run the anycast lab with lab.net's validator (CLI)

This needs read access to the private lab.net repository and Docker. lab.net's `validation-runner` image is the same engine its GitHub Action uses. The Academy pins lab.net commit `06c71623`, the commit its recorded runs were made with.

```bash
git clone https://github.com/exergy-connect/lab.net ../lab.net
git -C ../lab.net checkout 06c71623b044e5ee2d4a9bcfe052bc1b9fe7c6d2
docker build -f ../lab.net/go/Dockerfile --target validation-runner -t labnet-validator ../lab.net
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/workspace" -w /workspace labnet-validator \
  network/labnet/anycast-edge.xp --output validation/anycast-edge.pcapng --report validation/anycast-edge.json
```

```output
PASS ISP sessions to the IAH edge and to transit are up: isp_hou–cf_iah established AS13335; isp_hou–transit established AS64520
PASS ISP prefers the direct IAH peering for the anycast prefix: isp_hou bgp 192.0.2.0/24 via 10.1.0.1 as-path 13335
PASS Visitor reaches the anycast address at IAH: visitor echo 192.0.2.10 reply from web_iah
Wrote validation/anycast-edge.pcapng (198 captured records)
```

Open `validation/anycast-edge.pcapng` in Wireshark to see the BGP OPEN/UPDATE exchange and the ICMP echo on each simulated interface. Run the failover file the same way: the route check reports `as-path 64520 13335` and the reply comes from `web_dfw`.

lab.net's report keeps only each check's label and result. The Academy's figures also need the hop list and routing tables, so [academy/tools/labnet-path.mjs](repo:academy/tools/labnet-path.mjs) drives the same lab.net modules (`loadLab`, `startSimCluster`, `runValidation`) and keeps them. Run it inside the same image:

```bash
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/workspace" -w /workspace \
  -e LABNET_COMMIT=06c71623b044e5ee2d4a9bcfe052bc1b9fe7c6d2 --entrypoint node labnet-validator \
  academy/tools/labnet-path.mjs network/labnet/anycast-edge.xp --labnet /app --nodes isp_hou \
  --out academy/data/labnet/anycast-edge.json --pcap academy/data/labnet/anycast-edge.pcapng
git diff --stat academy/data/labnet/
```

```output
PASS ISP sessions to the IAH edge and to transit are up: isp_hou–cf_iah established AS13335; isp_hou–transit established AS64520
PASS ISP prefers the direct IAH peering for the anycast prefix: isp_hou bgp 192.0.2.0/24 via 10.1.0.1 as-path 13335
PASS Visitor reaches the anycast address at IAH: visitor echo 192.0.2.10 reply from web_iah
wrote academy/data/labnet/anycast-edge.json
```

lab.net is deterministic, so with the same lab.net commit and seed the committed files do not change and `git diff` prints nothing.

## 6. Change the topology and watch the decision change

Make IAH less attractive by prepending, or give transit a shorter path, and rerun step 5. For example, add a third edge with its own peering, or remove `isp_hou-transit` from the links list and confirm the visitor still reaches IAH. lab.net's route check messages tell you exactly which route the ISP holds.

::: pending 01-link-delay lab.net cannot yet report how many milliseconds each path takes, so this lab compares paths and hop counts, not latency.

## 7. Dry-run the cache rules and Tiered Cache

```bash
node security/waf/apply.mjs --file delivery/cache-rules.json | tail -1
```

```output
Dry run of delivery/cache-rules.json: 3 requests, 3 of 3 rules enabled. Nothing was sent. Re-run with --apply to change the zone.
```

Remove `| tail -1` to see each request body. With a zone: `CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ZONE_ID=... node security/waf/apply.mjs --file delivery/cache-rules.json --apply`.

## 8. On the deployed shop

These need a deployment. Replace the host with yours.

```bash
dig +short caddock-33audio.pages.dev
curl -sI https://caddock-33audio.pages.dev/ | grep -i -E 'cf-ray|cf-cache-status|server'
curl -s -o /dev/null -w 'dns %{time_namelookup}  connect %{time_connect}  tls %{time_appconnect}  ttfb %{time_starttransfer}  total %{time_total}\n' https://caddock-33audio.pages.dev/api/stock
```

`dig` returns Cloudflare anycast addresses, and `cf-ray` ends in the code of the data center that answered: the real-world counterpart of the lab.net anycast decision.
