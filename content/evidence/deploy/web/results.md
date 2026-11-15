# W8-LIVE-WEB: browser checks of the public URL

- Run: 2026-11-15, 21:50 to 21:57 KST (12:50 to 12:57 UTC), release 20261115T121537Z.
- URL: https://d3gct1libr2d5x.cloudfront.net/
- Driver: gstack headless Chromium (`$B`), new server process. No cookies and empty localStorage and sessionStorage before the first page.
- Load: one browser and 8 page loads over 7 minutes, with 3 API calls (parse, trend, scan). No burst.
- `content/evidence/deploy/release.json` still showed `failed` from the first run. The orchestrator checked the live state at 21:48 KST, so the run went ahead.

## Results

| # | Check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | `/` opens with no login | Pass. The language gate shows English and 한국어, with no account prompt. | 01-root.png |
| 2 | `/en/` and `/ko/` open with no login and no account prompt | Pass. Both show the start rail (Start investigating, Explore freely, Watch a demo) and the globe. The time slider reads 1981 to Sep 2026 (latest). | 02-en.png, 03-ko.png |
| 3 | Judge link `/ko/?demo=first-snow-seoul&at=result` opens on the verdict | Pass. It opens on step 8 of 10. The verdict card reads 감지된 추세 없음: Sen 1.5 days/decade, 95% CI -1.5 to 4.3, MK p 0.32, 1981 to 2025, 45 values, 40 more years needed. | 04-judge-ko.png |
| 4 | Judge link `/en/?demo=hot-days-phoenix&at=result` opens on the verdict | Pass. It opens on step 8 of 10. The verdict card reads Rising, significant: Sen 3.3 days/decade, 95% CI 1.4 to 5, MK p 0.0019. The CB-02 board is on the same panel. | 06-judge-en.png |
| 5 | Watch a demo: first-snow-seoul reaches the fallback with its 3 scan hits and their rates | Pass. 냉방도일 +53 degree-days/decade, 대기경계층 꼭대기 기압 +1.3 hPa/decade, 기온 +0.38 °C/decade. All 3 are "유의한 상승" and "훑어보기로 찾음". Nearby areas: 유의한 추세를 보이는 주변 지역이 없어요. Time to detect: 40 more years. | 08-ko-demo-fallback.png |
| 6 | Watch a demo: hot-days-phoenix reaches the CB-02 board | Pass. Case board on step 8. Driver: root-zone soil wetness, link test Consistent, r -0.34, p 0.023 (Seneviratne et al. 2010). Response: relative humidity, Consistent, r -0.49, p 0.00055 (Vicente-Serrano et al. 2018). The served `/demo/hot-days-phoenix/caseboard.json` has `board_id` CB-02. | 09-en-demo-caseboard.png |
| 7 | Live golden path in Korean with the first-snow question reaches the no-trend fallback | Pass. Typed 서울 첫눈이 늦어지고 있나요? and pressed 질문하기. `POST /api/v1/parse` returned 200 in 452 ms. The parser proposed 강설량 (PRECSNO), first date, at or above 0.1 mm/day, Seoul 25 km, 1981 onward. After 확인하고 분석하기, `GET /api/v1/trend` returned 200 in 486 ms. The result asked 추세처럼 보이나요?, and I chose 건너뛰기. Then `GET /api/v1/scan` returned 200 in 224 ms, and 3 stored results came from `/r/trend/*.json` (200). The verdict and fallback show the same values as the demo. | 13-ko-live-verdict.png, 14-ko-live-fallback.png |
| 8 | Failed requests and console errors | None. Every request returned 200 or 304. No console message at error level. | below |

## Failed requests and console messages

- Failed requests (status other than 200 or 304): none in any flow. `/demo/manifest.json` now returns 200 (it was 404 before the bundle).
- Console errors: none.
- Console warnings (not errors):
  - `PretendardVariable-s.p.0ztvx5mb7lxp4.woff2 was preloaded using link preload but not used within a few seconds`, once per page load.
  - `GL Driver Message ... GPU stall due to ReadPixels`, from the headless WebGL driver.

## Observations (not failed checks)

1. Closing card on a judge link. About 6 s after the judge link opens, the player moves to step 10 of 10. The closing card then covers the result (BORAMAE, NASA POWER · MERRA-2, the public URL). This is accepted item 26 and open decision 9 in TODOS.md. The card shows the CloudFront origin. Evidence: 05-judge-ko-fallback.png.
2. Pin offset on the live path. After the live result, the pin marker draws about 33 px above the area circle and its grid cell. The gap stays about 33 px in screen space after 3 and 5 keyboard zoom steps, so one layer is drawn with a fixed screen offset. In the demo, where the map flies in to zoom 8, the pin sits in the middle of the circle (04-judge-ko.png). I did not find the cause. A frontend owner should check it in W7-BROWSER-QA. Evidence: 13-ko-live-verdict.png, 15-ko-live-pin-zoom.png.
3. The API hit or miss value is not visible. CloudFront sets its own X-Cache header. This is the known deferred item, and I did not read response headers in this run.
