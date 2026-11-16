# Implementation Tracker

Status is evidence-based: COMPLETE only after code exists and its relevant automated verification has passed. IN PROGRESS means implementation exists but still needs a real local integration test.

| # | Workstream | Status | Completion evidence |
|---:|---|---|---|
| 1 | Audit source repository and dependencies | COMPLETE | Repository tree, source modules, test inventory and render report inspected |
| 2 | Establish channel working repository | COMPLETE | Fork verified; write permission confirmed |
| 3 | Channel configuration and editorial identity | COMPLETE | Channel config, editorial constitution, production plan and fixed decisions committed |
| 4 | Daily topic discovery and scoring | COMPLETE | Query-based Google News RSS scouting across India, UK and US editions, topic scoring, clustering, publisher URL resolution and CI tests |
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

The latest channel-critical GitHub Actions workflow passed on commit 44840413f8922d09ecf066f04ba7226315e34af3 (run 43901893248): **352 tests passed, 0 failed**, in 1296.71 seconds (21 minutes 36 seconds) for the test suite. The complete workflow ran from 15:56:19Z to 16:18:44Z. This verifies the 2-fps long-form test proxy optimization, publisher approval-safety tests, daily-job orchestration, research/provenance and redirect-target security regressions, production/QC, packaging, local inference, scheduling, Python compilation, CLI help and zsh launcher syntax. Production video settings remain unchanged; the proxy is test-only.

The test suite runtime improved from 2172.83 seconds (36m12s) on commit d3645a83ade2c7c49b62c4934f2c2f9c5af2f70e to 1296.71 seconds (21m36s), reducing runtime by approximately 40%. The 40-minute CI timeout now has comfortable headroom.

The run emitted 15,168 Pillow deprecation warnings from `Image.Image.getdata` at `src/ai_video_factory/production.py:272` (15,166 daily-job warnings and 2 production warnings). These did not fail tests. Replace the deprecated API with its supported equivalent and retain image-analysis behavior in a follow-up cleanup.

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
