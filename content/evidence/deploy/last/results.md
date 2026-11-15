# W8-LIVE-LAST results

Run 2026-11-15, 22:03 to 22:10 KST (13:03 to 13:10 UTC), against the public URL `https://d3gct1libr2d5x.cloudfront.net/`, release 20261115T121537Z. Python urllib sent the HTTP requests. gstack headless Chromium (`$B`) opened the pages. The run used AWS profile `devcdlee` (account 177950257164) for every AWS call.

`content/evidence/deploy/release.json` shows the status `deployed` and is not static-only, so the zero-task part applies.

## Summary

| Check | Result | Evidence |
| --- | --- | --- |
| Zero-task demo check (approved write 7) | **Not run (denied).** The auto mode permission check denied the scale-to-zero command. The service did not change. | "Zero-task check" below |
| Service at 1 or more tasks with `/health` 200 before the 429 burst | Pass. 1 of 1 tasks running, scaling range 1 to 2, at 22:04:29 KST. `/health` 200 at 22:05:01 KST. | `probes.jsonl` |
| A blocked request shows HTTP 429 | **Pass: 429.** Request 146 of the burst, at 22:05:44 KST | `burst-parse.jsonl`, WAF samples |
| Pages and demos still answer from the blocked IP | Pass. `/health`, `/ko/`, `/en/`, `/meta/catalog.json` and the demo files answer 200. Both judge links reach their verdict and their fallback or board. | `probes.jsonl` |
| End of the parse block | The block ended between 22:10:04 and 22:10:24 KST, about 4 min 40 s after the first 429. | `blockend-parse.jsonl` |

## Zero-task check (approved write 7): not run (denied)

Read-only start state at 22:04:29 KST: `aws ecs describe-services --cluster default --services boramae-api` gives status ACTIVE, desiredCount 1, runningCount 1, pendingCount 0. `aws application-autoscaling describe-scalable-targets` gives `service/default/boramae-api` with MinCapacity 1 and MaxCapacity 2. The ApiServiceArn output confirms cluster `default` and service `boramae-api`.

The scale-to-zero command was tried once at about 22:04 KST. The Claude Code auto mode permission check denied it ("Destructive or Unwanted Actions"). The command did not run. As the orchestrator note says, it was not retried. A read-only check right after showed the same state: 1 of 1 tasks running, range 1 to 2.

What this run shows without the zero-task state:

- The two judge links read only `/demo/` and `/basemap/` files from the web bucket (network lists of both pages below). Neither link requests an API-origin path (`/api/*`, `/r/*`, `/meta/*`).
- The start page `/ko/` requests `/meta/catalog.json` (200, 522 ms) on load, and that path goes to the API origin. CloudFront caches it with `max-age=300, stale-while-revalidate=300`. So the start page, which holds the "Watch a demo" button, reads a path that needs a running task or a cached copy. It is not verified whether the demo door still works when that request fails. Only the zero-task check can show it.

### Commands for the user

Run these in your own terminal, in this order. Step 4 brings the API back. Until you run it, every live question fails.

```bash
# 1. Scale the API to 0 tasks (approved write 7).
MSYS_NO_PATHCONV=1 aws application-autoscaling register-scalable-target --service-namespace ecs --resource-id service/default/boramae-api --scalable-dimension ecs:service:DesiredCount --min-capacity 0 --max-capacity 0 --profile devcdlee --region us-west-2

# 2. Wait until runningCount is 0 (repeat until it prints 0).
aws ecs describe-services --cluster default --services boramae-api --profile devcdlee --region us-west-2 --query "services[0].runningCount"

# 3. With 0 tasks, open both judge links, and play both demos from the start pages
#    (/ko/ then 데모 보기, and /en/ then Watch a demo). Each must reach its verdict,
#    and its fallback (first snow) or its case board (Phoenix).
#    https://d3gct1libr2d5x.cloudfront.net/ko/?demo=first-snow-seoul&at=result
#    https://d3gct1libr2d5x.cloudfront.net/en/?demo=hot-days-phoenix&at=result

# 4. Restore the minimum of 1 task. Do not skip this step.
MSYS_NO_PATHCONV=1 aws application-autoscaling register-scalable-target --service-namespace ecs --resource-id service/default/boramae-api --scalable-dimension ecs:service:DesiredCount --min-capacity 1 --max-capacity 2 --profile devcdlee --region us-west-2

# 5. Wait until runningCount is 1 and GET https://d3gct1libr2d5x.cloudfront.net/health answers 200.
aws ecs describe-services --cluster default --services boramae-api --profile devcdlee --region us-west-2 --query "services[0].runningCount"
```

## 429 check (approved write 8)

The edge web ACL `boramae-edge-b2fbde84266c` has the rule `rate-parse`. It limits `POST /api/v1/parse` to 100 requests for each client IP in a 300-second window (`infra/lib/edge-acl.ts`, `EvaluationWindowSec` 300). Its block action sends a custom response code 429.

- Before the burst: `GET /health` gave 200 at 22:05:01 KST.
- Burst: one request after the other, each `POST /api/v1/parse` with the body `{"text": "서울 첫눈", "lang": "ko", "session_id": "w8livelast01"}` and `Content-Type: application/json`. The first request went at 22:05:02 KST.
- Requests 1 to 145 answered 200. **Request 146 answered 429** at 22:05:44 KST, 42.7 s after the first request. The client then stopped the burst. The 1-per-second tail was not needed.
- The 429 answer has an empty body, no `Content-Type` and `X-Cache: Error from cloudfront`.
- The WAF accepted 45 requests over the limit of 100 before the block started. A rate rule counts in the background, and a block starts some time after the count passes the limit.
- Read-only `aws wafv2 get-sampled-requests` (scope CLOUDFRONT, us-east-1, rule metric `rate-parse`, 22:00 to 22:07:30 KST): population 4, all action BLOCK, `POST /api/v1/parse`, response code 429. The first sample is at 22:05:44.897 KST, which is request 146. The other three are the first polls of the block-end check.

### While the parse path was blocked

From the same IP, 22:06:11 to 22:07:55 KST:

| Request | Status | X-Cache |
| --- | --- | --- |
| `GET /health` | 200 | Miss from cloudfront |
| `GET /ko/` | 200 | Hit from cloudfront |
| `GET /en/` | 200 | Hit from cloudfront |
| `GET /meta/catalog.json` | 200 | Hit from cloudfront |
| `GET /demo/manifest.json` | 200 | Hit from cloudfront |
| `GET /demo/first-snow-seoul/trend.json` | 200 | Miss from cloudfront |
| `GET /demo/first-snow-seoul/scan.json` | 200 | Miss from cloudfront |
| `GET /demo/hot-days-phoenix/trend.json` | 200 | Miss from cloudfront |
| `GET /demo/hot-days-phoenix/caseboard.json` | 200 | Miss from cloudfront |

One extra probe asked for `/demo/first-snow-seoul/caseboard.json` and got 403. That file does not exist, because the first-snow demo ends on the fallback, and S3 behind origin access control answers 403 for a missing key. The path was my wrong guess. It is not a failure, and `probes.jsonl` leaves it out.

Judge links in the browser, during the block:

- `/ko/?demo=first-snow-seoul&at=result` (22:06:53 KST): step 8 of 10. The verdict card shows 감지된 추세 없음, Sen 10년당 1.5일, 95% CI 10년당 -1.5일 to 4.3일, MK p 0.32, 1981 to 2025, 45 values, 40년 더. The fallback shows the 3 scan hits (냉방도일, 대기경계층 꼭대기 기압, 기온) and no nearby areas. No console errors. All 26 requests answered 200 or 304. Requests outside `/_next/static/`: the page, `/basemap/` (3 files), `/demo/manifest.json`, `/demo/catalog.json` and `/demo/first-snow-seoul/` (6 files).
- `/en/?demo=hot-days-phoenix&at=result` (22:07:05 KST): step 8 of 10. The verdict card shows Rising, significant, Sen 3.3 days per decade, 95% CI 1.4 to 5, MK p 0.0019. The case board shows the driver Root-zone soil wetness (Consistent, r -0.34, p 0.023) and the response Relative humidity (Consistent, r -0.49, p 0.00055). No console errors. Requests outside `/_next/static/`: the page, `/basemap/` (3 files), `/demo/manifest.json`, `/demo/catalog.json` and `/demo/hot-days-phoenix/` (3 files), all 200.

These values are the same as in `content/evidence/deploy/web/results.md`.

### End of the block

After the burst, one `POST /api/v1/parse` went every 20 s, 13 in all, far under the limit. The 12 polls from 22:06:23 to 22:10:04 KST answered 429. The poll at 22:10:24 KST answered 200 (487 ms, `application/json`), so the block ended between those two times. That is about 5 min after the first burst request at 22:05:02 KST, which matches the 300-second window. At 22:10:20 KST, a read-only `describe-services` showed 1 of 1 tasks running, and `/health` answered 200 at 22:10:22 KST.

## Files

- `burst-parse.jsonl`: one line per burst request (time, status, ms, X-Cache).
- `blockend-parse.jsonl`: the parse polls after the burst, one every 20 s.
- `probes.jsonl`: the GET probes before the write attempt and during the block.

No AWS write ran in this package. The only AWS write it tried (approved write 7) was denied. Every other AWS call was read-only.
