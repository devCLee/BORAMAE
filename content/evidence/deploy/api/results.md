# W8-LIVE-API results

Run 2026-11-15, 21:54 to 22:00 KST (12:54 to 13:00 UTC), against the public URL `https://d3gct1libr2d5x.cloudfront.net/`. 10 HTTP requests in total, one after another: 9 through the distribution and 1 to the origin. Python urllib with its default user agent sent them. No request carried the origin header, and no file holds its value. `results.json` holds every value below.

At the start, `content/evidence/deploy/release.json` still showed the status `failed` of the first run. The orchestrator note says that W8-RECORD rewrites that file, and the orchestrator verified the live state at 21:48 KST, so this run went on.

## Summary

| Check | Result | Evidence |
| --- | --- | --- |
| `GET /health` through the distribution | Pass: 200 `{"status":"ok"}` | Server-Timing `total;dur=0.4` |
| Stored result by key | Pass: 200, 17,607 bytes | `/r/trend/04950cfc7428ea3006fe8e654ba69bf8.json`, `X-Result-Key` equal to the key |
| `GET /meta/catalog.json` | Pass: 200, 20 variables | `Cache-Control: public, max-age=300, stale-while-revalidate=300` |
| Server-Timing, new monthly area | Pass: 133.8 ms total on a cold read (budget 20 s) | Nairobi T2M, 674,578 bytes fetched |
| Server-Timing, first snow | Pass: 186.0 ms total on a cold read | Sapporo PRECSNO, 1,446,912 bytes fetched |
| Origin lock | Pass: 403 | Web ACL sample: rule `require-edge-header`, BLOCK, `GET /health` |
| Create-once rule (approved write 6) | Pass: `PreconditionFailed` (412) | The object's ETag and VersionId did not change |
| Spend projection until Jan 27, 2027 | About 196 USD (base case). Every month stays under the 100 USD budget | December, at 83.27 USD, passes the 80 USD alert line |

## Stored result and catalog

- `/r/trend/04950cfc7428ea3006fe8e654ba69bf8.json` (a key from `api/.data-demo/r/trend/`): 200 `application/json`, `Cache-Control: public, max-age=31536000, immutable`, `X-Cache: Hit from cloudfront`, `Age: 355`. The body has `spec.ds` `power-merra2-monthly@2026-09` and the verdict `significant_fall`.
- `/meta/catalog.json`: 200 `application/json`, 20,219 bytes, 20 variables, `X-Cache: Hit from cloudfront`.

## Server-Timing

Each spec was built as the web client builds it: the canonical JSON of a `RequestSpec` in base64url with no padding (docs/BUILD_CONTRACT.md "The query parameter `s`"). The window is `{start: 1981, end: "latest"}` and the radius is 25 km. The codec is `boramae.contracts.spec.encode_request_spec`, and the Seoul spec reproduces golden vector 1 of `content/golden/request-spec.json` exactly. Before the requests, each key was derived against the demo catalog. The bucket listing (read-only) did not hold any of the new keys.

| Request | Store | Server-Timing | X-Bytes-Fetched | Verdict |
| --- | --- | --- | --- | --- |
| T2M annual mean, Busan (35.1796, 129.0756) | miss | `read;dur=329.7, stats;dur=6.0, total;dur=443.8` | 0 | significant_rise |
| Same spec again | hit (written by the request before) | `total;dur=20.1` | 0 | significant_rise |
| PRECSNO first snow, Chuncheon (37.8813, 127.7298) | miss | `read;dur=31.1, stats;dur=8.0, total;dur=91.5` | 0 | no_trend |
| PRECSNO first snow, Seoul (golden vector 1) | hit (demo store) | `total;dur=19.7` | 0 | no_trend |
| T2M annual mean, Nairobi (-1.2921, 36.8219) | miss, cold read | `read;dur=82.5, stats;dur=5.8, total;dur=133.8` | 674,578 | significant_rise |
| PRECSNO first snow, Sapporo (43.0618, 141.3545) | miss, cold read | `read;dur=130.6, stats;dur=7.7, total;dur=186.0` | 1,446,912 | no_trend |

- The two values for the record are the cold reads: **monthly new area 133.8 ms** and **first snow 186.0 ms**, both on the deployed task. Both are far under the 20 s budget for a new area. Wall time at the client was 0.73 s and 0.39 s.
- The first two store misses (Busan, Chuncheon) fetched 0 bytes, because the task's chunk cache already held their chunks. The stored Chuncheon result reads 3 daily chunks of 1,249,577 bytes. That equals the footprint of result `246e0e4523e15f62a85a5c8d9da8247d` (Seoul PRECSNO, written 21:51 KST by an earlier live check), and both cells fall in the same 15 x 15 chunk block. It is not verified which earlier request loaded the Busan monthly chunk. The two cold-area requests (Nairobi, Sapporo) were added to measure a real read from POWER. On those, X-Bytes-Fetched equals the stored bytes of the footprint.
- The Busan answer carries `X-Containing-Cell: true`.
- The repeat of the Busan spec took 20.1 ms with no read phase. So the miss wrote its result to the store once, and the next request read it back.
- `X-Cache` shows only the CloudFront value (`Miss from cloudfront` on every `/api/v1/trend` request, which is uncached). The API value `hit` or `miss` does not reach the client. This is a known item, deferred until after the submission, and not a failure here.

## Origin lock

`GET https://bo-5cf93111162a4ce89e2798885606c03f.ecs.us-west-2.on.aws/health`, sent with no origin header, answered **403** `text/html` with the page "403 Forbidden". A read-only `wafv2 get-sampled-requests` call on the regional web ACL `EdgeOriginGuard2A455CAF-km3o2ELFDkg9`, rule metric `require-edge-header`, from 12:50 to 13:10 UTC, gives population 1: action BLOCK, `GET /health` at 21:54:20 KST. That is this request.

## Create-once rule (approved write 6)

The one AWS write of this package. It ran once and was not denied.

```
aws s3api put-object --bucket boramae-databuckete3889a50-34ucz49awzhz \
  --key r/trend/04950cfc7428ea3006fe8e654ba69bf8.json \
  --body <scratch copy of api/.data-demo/r/trend/04950cfc7428ea3006fe8e654ba69bf8.json> \
  --if-none-match "*" --profile devcdlee --region us-west-2
```

Exact error (CLI exit code 254):

```
aws: [ERROR]: An error occurred (PreconditionFailed) when calling the PutObject operation: At least one of the pre-conditions you specified did not hold
```

`PreconditionFailed` is the S3 error code of HTTP 412. The CLI does not print the status line. The body was a byte copy of the same stored file, so the object would have kept its content even if the condition had not held. Read-only `head-object` and `list-object-versions` calls, before and after the put, show the same state: ETag `7a1610aa4977c1b68cb1b98f525c3884`, VersionId `cGBrWqVDh2MRky0EHr8sF0Z3mwcT5VV8`, 1 version. No new version was written.

## Spend projection until Jan 27, 2027

Read-only inventory at 22:00 KST, from the CLI with profile `devcdlee`:

- Stack `Boramae`: 26 resources, all CREATE_COMPLETE.
- Express service `boramae-api`: ACTIVE, 1 of 1 tasks running, ARM64 Fargate with 1 vCPU and 2 GB, scaling 1 to 2 tasks.
- 1 internet-facing Application Load Balancer, `ecs-express-gateway-alb-6e0c1462`, in 2 Availability Zones.
- 4 public IPv4 addresses: 3 Elastic IPs on the load balancer interfaces and 1 on the task interface.
- 2 web ACLs with 6 rules. The regional ACL has `require-edge-header`. The edge ACL has 3 AWS managed rule groups, `rate-parse` and `rate-spec`.
- CloudFront `PriceClass_200`.

Prices: the us-west-2 list prices in TODOS.md "Deploy session decisions". Fargate Arm costs $0.03238 per vCPU-hour and $0.00356 per GB-hour. The load balancer costs $0.0225 per hour plus $0.008 per LCU-hour. Public IPv4 costs $0.005 per hour. WAF costs $5 per web ACL and $1 per rule a month. The window runs from 2026-11-15 12:40 UTC (the stack create) to the end of Jan 27, 2027 KST, which is 1,754.3 hours.

| Case | Per 730-hour month | Nov 2026 | Dec 2026 | Jan 2027 (to the 27th) | Total until Jan 27 |
| --- | --- | --- | --- | --- | --- |
| Low: 1 task, 0.1 LCU | 76.44 | 38.89 | 77.91 | 66.91 | 183.71 |
| Base: 1 task, 1 LCU | 81.70 | 41.56 | 83.27 | 71.52 | 196.34 |
| High: 2 tasks all the time, 1 LCU | 114.19 | 58.08 | 116.37 | 99.95 | 274.41 |

All values are USD. Compared with the 100 USD monthly budget (`MonthlyBudget-us-west-2-HQeg0rcUxCa7`, one alert at 80% of actual spend):

- Base case: every calendar month stays under 100 USD. The full month of December, at 83.27 USD, passes the 80 USD alert line, so expect that alert late in December. The low case, at 77.91 USD, stays under it.
- High case: 2 tasks for all of December would cost 116.37 USD, over the budget. The scaling goes to 2 tasks only at 60% CPU.
- TODOS.md estimated about 74 USD a month and 178 USD in total, before the deploy. The created stack has 4 public IPv4 addresses (14.60 USD a month) and 6 WAF rules (6 USD a month). TODOS.md does not say how many of each it counted.
- At the check, the budget's actual spend was 0.0 USD. Budget data lags, and the stack was 20 minutes old.
- Not priced, because the TODOS.md list has no price for them: the Secrets Manager secret, CloudWatch Logs (1 log group, 0 bytes stored, 90-day retention), S3 storage and requests (2 versioned buckets), ECR image storage, the custom-resource Lambda, WAF requests at $0.60 per million, CloudFront (inside the always-free tier at this traffic), and the alarm and certificate that Express made. At this traffic they should be small. The real bill is the check.
