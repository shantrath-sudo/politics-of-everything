# Implementation Tracker

Status is evidence-based: COMPLETE only after code exists and its relevant automated verification has passed. IN PROGRESS means implementation exists but still needs a real local integration test.

| # | Workstream | Status | Completion evidence |
|---:|---|---|---|
| 1 | Audit source repository and dependencies | COMPLETE | Repository tree, source modules, test inventory and render report inspected |
| 2 | Establish channel working repository | COMPLETE | Fork verified; write permission confirmed |
| 3 | Channel configuration and editorial identity | COMPLETE | Channel config, editorial constitution, production plan and fixed decisions committed |
| 4 | Daily topic discovery and scoring | IN PROGRESS (provider resilience) | Live scout run [44104453892](https://github.com/shantrath-sudo/politics-of-everything/actions/runs/44104453892) succeeded on e2afb463. Live report: 167 headlines; The Hindu 60, Guardian World 45, BBC India 22, PIB 20, NPR 10, Business Standard 10; 164 clusters, 12 duplicates filtered, 152 remaining clusters, 30 shortlisted candidates. PIB national RSS feed is now contributing. GDELT still returns HTTP 429; RSS fallback is healthy. Latest full test run 44104477139 is still running. |
| 5 | Duplicate detection and topic ledger | COMPLETE | Covered-topic ledger checked during scouting; updated only after final approval |
| 6 | Research dossier and source-quality rules | IN PROGRESS | HTTPS-only research transport validates every redirect destination, blocks private/loopback/link-local/reserved hosts, caps redirects/body size and enforces bounded request deadlines; real publisher fetch/extraction still needs Mac smoke test |
| 7 | Claim ledger and corroboration | IN PROGRESS | Source, claim, contradiction and verified-fact artifacts integrated; verbatim evidence grounding and two independent reliable publisher domains required for promotion; real dossier not yet generated |
| 8 | 10–15 minute script engine | COMPLETE | Runtime limits, political documentary prompt, longer research context and CI tests |
| 9 | Topic/script/final approval gates | COMPLETE | Persistent fail-closed state transitions; explicit topic, script and final approval commands |
| 10 | Local narration and Mac resource profile | IN PROGRESS | 4B-class local inference profile configured; model and TTS need installation/readiness test |
| 11 | Visual sourcing and rights manifest | IN PROGRESS | Wikimedia Commons CC0/PD/CC-BY/CC-BY-SA acquisition and combined attribution manifest wired; needs live asset test |
| 12 | Remotion/FFmpeg production profile | IN PROGRESS | Approved long-form script input, licensed Commons visuals and 12 GiB disk guard wired into renderer; no real Mac render yet |
| 13 | Technical/editorial quality gates | IN PROGRESS | Existing QC pipeline retained; real documentary render and review required |
| 14 | Sunday delivery package | IN PROGRESS | Private Sunday package assembly, MP4 hard-link/copy, research, script, captions and attribution tested; real render artifacts still need audit |
| 15 | Daily/weekly macOS scheduling | IN PROGRESS | daily scouting, four-hour advancement and Sunday delivery launchd templates (Sunday correctly uses Weekday=0), system-timezone guard, one-command bootstrap, install/uninstall scripts and macOS approval notifications committed; not installed or activated |
| 16 | Pilot: Who Really Controls a Democracy? | PENDING | Requires researched dossier, approved script, render, QA and editor sign-off |
| 17 | Operational activation | PENDING | Requires local setup, full rehearsal and explicit user go-ahead; publishing remains disabled |

## Verified CI

- 2026-11-17 discovery iteration: full channel workflow run [44088470166](https://github.com/shantrath-sudo/politics-of-everything/actions/runs/44088470166) passed on commit `3b877053611fbfb84fba58cfafec454452cd763e`. All steps passed: zsh launcher syntax, dependency installation, Python compilation, CLI check and channel/inference test suite. The live topic scout run [44088369719](https://github.com/shantrath-sudo/politics-of-everything/actions/runs/44088369719) passed on the preceding source commit `e6edf9a3ed56379e2841f7eaa9223c8d1ef536fd`.
- The live scout report returned 149 headlines: The Hindu 60, Guardian World 45, BBC India 23, NPR 10, Business Standard 11; GDELT DOC returned HTTP 429 and Indian Express returned HTTP 403. It produced 147 clusters and 30 candidates. This is enough to validate fallback operation, but not enough to declare all providers reliable.

The latest channel-critical GitHub Actions workflow passed on commit 4df69a032ad7dec5091d92add508fddf1ddb2190 (run 43906366803): **352 tests passed, 0 failed**, in 1247.11 seconds (20 minutes 47 seconds) for the test suite. The complete workflow finished successfully at 16:42:27Z. This verifies the Pillow pixel-access deprecation cleanup in addition to the 2-fps long-form test proxy optimization, publisher approval-safety tests, daily-job orchestration, research/provenance and redirect-target security regressions, production/QC, packaging, local inference, scheduling, Python compilation, CLI help and zsh launcher syntax. Production video settings remain unchanged; the proxy is test-only.

The test suite runtime improved from 2172.83 seconds (36m12s) on commit d3645a83ade2c7c49b62c4934f2c2f9c5af2f70e to 1296.71 seconds (21m36s), reducing runtime by approximately 40%. The 40-minute CI timeout now has comfortable headroom.

The Pillow deprecation cleanup replaced `Image.Image.getdata` with `gray.tobytes()` in `src/ai_video_factory/production.py`. The follow-up CI run passed all 352 tests; the pytest output contained no Pillow deprecation warnings. GitHub Actions also emitted a separate Node.js 20 deprecation notice for its workflow actions; this is an upstream CI-runtime warning, not a Python test warning.

This CI verifies repository code on GitHub's Linux runner; it does not prove a live Mac render, real-source research run, actual local model inference or local TTS.

## Research audit notes

- The research production path fetches actual source text and refuses URL-only extraction.
- Extracted claims must include verbatim quotes grounded inside a selected source-text slice.
- Promotion requires supported claim labels, no detected unresolved contradiction, and two independent reliable publisher domains.
- The redirect fix validates each hop before the next request. DNS is resolved for validation and then resolved again by the HTTP client at connection time; DNS rebinding is therefore a residual hardening concern, not a guarantee of complete SSRF immunity.
- The separate citation URL verifier still uses urllib's automatic redirect handling; it verifies liveness rather than extracting source content, but its redirect behavior remains part of the security audit.

## Fixed configuration
- Channel: Politics of Everything
- Working branch: channel/bootstrap
- Language: English
- Runtime: 10–15 minutes; target 12.5
- Delivery: Sunday
- Timezone: Asia/Kolkata
- Topic scouting: daily at 08:00 when launchd is installed
- Workflow advancement: every 4 hours when launchd is installed
- Publishing: OFF
- Paid APIs/services: OFF pending explicit approval
- LTX-2 / large video models: DO NOT INSTALL


## Topic discovery provider switch (2026-11-17)

- Google News RSS and its redirect-resolution dependency have been removed from the scouting path.
- Primary discovery: one GDELT DOC ArticleList JSON request per scout, using a 24-hour search window and the channel's combined topic vocabulary.
- Independent fallback/breadth: direct RSS feeds from BBC India, The Hindu, Indian Express, Business Standard, The Guardian World and NPR.
- All candidate links must be credential-free HTTPS URLs and pass the existing blocked/private-host check before entering the shortlist.
- GDELT and publisher feeds are discovery inputs only. The separate research pipeline remains responsible for fetching, extracting, corroborating and verifying claims.
- GDELT attribution: https://www.gdeltproject.org/ . No API key, paid API or BigQuery dependency is introduced.


## Discovery quality iteration (2026-11-17)

- The latest live run exposed two provider failures (GDELT HTTP 429 and Indian Express HTTP 403) while the remaining RSS feeds supplied 149 headlines.
- Added per-provider headline counts so future reports identify which feeds contribute results, rather than only showing a combined total. Latest verified counts: The Hindu 60, Guardian World 45, BBC India 23, NPR 10 and Business Standard 11.
- Added a conservative ranking penalty for obvious lifestyle/sports/celebrity signals only when a headline has no substantive political or institutional signal. This is a ranking adjustment, not an automatic rejection; editorial review remains mandatory.
- Regression tests cover political-story ranking ahead of sports/lifestyle noise and provider-level diagnostics.
- The latest live shortlist confirms the ranking correction: the basketball noise story moved to rank 20 after the generic `state` and `law` false-positive terms were removed. The full test suite now includes the regression case and passes. GDELT retry/backoff is implemented and tested, but a live HTTP 429 still prevented GDELT contribution in this run.

## Primary-source discovery fallback (2026-11-17)

- Removed the Indian Express RSS endpoint from the scout after the live GitHub runner received HTTP 403.
- Added the official Press Information Bureau (Government of India) Press Releases RSS endpoint as a primary-source discovery input. The official PIB RSS index lists the regional feed format; the first live run showed the all-region `Regid=1` endpoint returned zero headlines, so the feed now uses the active national feed `Regid=3`: https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3.
- PIB releases are government-originated leads, not independent journalism. The discovery source-diversity score explicitly excludes PIB so its presence cannot inflate the independent-publisher signal.
- Regression tests assert the new feed is requested, the blocked Indian Express endpoint is absent, and PIB does not count as an independent publisher.
- Live validation completed in run [44104453892](https://github.com/shantrath-sudo/politics-of-everything/actions/runs/44104453892): the corrected national PIB RSS feed contributed 20 headlines. Total discovery rose to 167 headlines; 164 clusters were formed, 12 duplicates were filtered against the ledger, and 30 candidates were shortlisted from 152 remaining clusters. GDELT still returned HTTP 429, but all six direct RSS feeds (including PIB) supplied 167 headlines. The feed fallback is therefore validated; GDELT remains an optional degraded provider, not a blocker.
- The approved first pilot was bootstrapped successfully in run [44104453920](https://github.com/shantrath-sudo/politics-of-everything/actions/runs/44104453920): `poe-2026-11-17-pilot-democracy`, stage `topic_approved`; script and final approvals remain false. The artifact contains four curated source URLs across Freedom House, International IDEA, PRS Legislative Research and The Indian Express.
- Latest full test run [44104477139](https://github.com/shantrath-sudo/politics-of-everything/actions/runs/44104477139) is executing after the PIB endpoint correction and regression assertion.
