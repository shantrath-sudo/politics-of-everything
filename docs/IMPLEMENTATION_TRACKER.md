# Implementation Tracker

Status is evidence-based: COMPLETE only after code exists and its relevant automated verification has passed. IN PROGRESS means implementation exists but still needs a real local integration test.

| # | Workstream | Status | Completion evidence |
|---:|---|---|---|
| 1 | Audit source repository and dependencies | COMPLETE | Repository tree, source modules, test inventory and render report inspected |
| 2 | Establish channel working repository | COMPLETE | Fork verified; write permission confirmed |
| 3 | Channel configuration and editorial identity | COMPLETE | Channel config, editorial constitution, production plan and fixed decisions committed |
| 4 | Daily topic discovery and scoring | COMPLETE | Query-based Google News RSS scouting across India and US editions, topic scoring, clustering, publisher URL resolution and CI tests |
| 5 | Duplicate detection and topic ledger | COMPLETE | Covered-topic ledger checked during scouting; updated only after final approval |
| 6 | Research dossier and source-quality rules | IN PROGRESS | Secure research pipeline uses political/institutional source profiles and channel-relevant excerpt selection; real publisher fetch/extraction still needs Mac smoke test |
| 7 | Claim ledger and corroboration | IN PROGRESS | Source, claim, contradiction and verified-fact artifacts integrated; verified facts require two independent reliable publisher domains; real dossier not yet generated |
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
The channel-critical GitHub Actions workflow passed on commit 9c76bd7d: 159 tests passed. Coverage includes topic discovery/workflow (India + international RSS editions), readable shortlist reports, political excerpt selection, reliable independent-source corroboration, channel CLI approval and revision cycles, delivery, Sunday launchd scheduling, long-form duration, format, local model smoke-test lifecycle, scheduler and inference tests, plus Python compilation and zsh launcher syntax checks. This verifies repository code in CI; it does not prove a live Mac render, real-source research run, actual local model inference or local TTS.

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
