# Politics of Everything

A local-first documentary production system for the Politics of Everything YouTube channel. It is based on the MIT-licensed AI Video Factory repository and adapted for evidence-led political documentaries.

## Fixed channel specification

- English-language documentaries for an international audience, with meaningful India context.
- 10–15 minutes; target 12.5 minutes.
- One finished documentary delivered every Sunday.
- Professional documentary motion graphics.
- Editorial identity: accessible, intellectually rigorous, non-partisan and evidence-led.
- First pilot: Who Really Controls a Democracy?
- Daily topic scouting; weekly research, scripting, narration, editing and quality review.
- Human approval is mandatory for topic, script and final video.
- Public upload and publication are disabled.

Read CHANNEL.md, EDITORIAL_CONSTITUTION.md, PRODUCTION_PLAN.md, and docs/DECISIONS.md before changing channel behaviour.

## Current implementation

### Local topic scouting and editorial state

The politics-channel command uses one free GDELT DOC ArticleList search over a 24-hour window, combined with direct RSS feeds from BBC India, The Hindu, Indian Express, Business Standard, The Guardian World and NPR. It validates direct HTTPS publisher links, clusters related headlines and scores candidates. It requires no API key and makes no paid API calls.

    politics-channel start-pilot
    politics-channel scout
    politics-channel status

The scout saves a dated JSON report and a readable Markdown shortlist under data/channel/scouting/. Discovery scores are prioritisation signals only; they are not fact checks. A candidate becomes a project only after explicit topic approval:

    politics-channel approve-topic CANDIDATE_ID

The project workflow enforces this order:

1. Topic approval
2. Research from at least two independent publisher domains
3. Claim extraction, corroboration and contradiction checks
4. Documentary script generation and topic-adherence check
5. Script approval
6. Remotion/FFmpeg rendering and technical QA
7. Final MP4 submitted for approval
8. Final editorial approval

Commands:

    politics-channel scout --limit 20
    politics-channel model-check
    politics-channel status
    politics-channel approve-topic CANDIDATE_ID
    politics-channel research PROJECT_ID
    politics-channel draft-script PROJECT_ID
    politics-channel approve-script PROJECT_ID
    politics-channel request-revision PROJECT_ID "Describe required changes"
    politics-channel render PROJECT_ID
    politics-channel approve-final PROJECT_ID
    politics-channel advance
    politics-channel deliver --force  # manual test only; normally Sunday at 09:00

The advance command runs only non-approval stages and stops at every human gate. When research or writing is due, it starts the configured local model if needed and unloads it only if the automation started it. The Sunday delivery command assembles a private review package under data/deliveries/. It contains the final MP4 and available research, script, attribution, captions and QA artifacts. The final approval command only records editorial approval. It does not upload or publish.

### macOS scheduling

After installing LM Studio and bootstrapping its `lms` command, the one-command setup is:

    zsh scripts/bootstrap_mac.sh

It installs missing Homebrew tools, the local model, Kokoro, Remotion dependencies, runs a real model-completion smoke test and registers the three launchd jobs. If you have already completed those steps manually, you can install only the schedules with:

    zsh scripts/install_launchd.sh

This installs daily scouting at 08:00, workflow advancement every four hours, and private delivery every Sunday at 09:00. To remove the schedules without deleting project data:

    zsh scripts/uninstall_launchd.sh

The Mac must be awake and the user session available for local work. Logs are written to data/logs/. Do not install the schedules until the local model and media toolchain have passed their readiness checks.

### Production engine

The existing research pipeline, Remotion, FFmpeg, narration and quality-control components are retained. GDELT and publisher RSS are discovery inputs only; they do not establish factual accuracy. The research stage independently fetches and extracts publisher source text, requires at least two distinct publisher domains, and writes source, claim, contradiction and verified-fact records. The long-form script engine and format presets are configured for 10–15 minute documentaries. Local inference and Kokoro narration have been installed and smoke-tested on the configured Mac.

## Safety

- The legacy scheduler run YouTube uploader is disabled for this channel.
- No YouTube credentials are required for topic scouting or local review.
- No paid service or hosted inference provider is activated by default.
- No large generative-video model weights should be downloaded.
- No topic, script or final video is automatically approved.
- No public upload or publishing occurs.

## Development

Requires Python 3.12 and the project's existing uv/FFmpeg/Remotion prerequisites. The repository CI runs the channel-critical tests on pushes to channel/bootstrap.

See docs/LOCAL_SETUP.md for the one-time Mac setup, model and TTS installation, and launchd activation. See docs/IMPLEMENTATION_TRACKER.md for verified progress and outstanding work.


### Topic discovery sources

Topic scouting uses the free GDELT DOC API (24-hour ArticleList search) and direct publisher RSS feeds. Google News RSS and Google News redirect resolution are not used. GDELT is a discovery index, not a verification source; all reporting still passes through the channel's existing research and editorial approval workflow. GDELT project: https://www.gdeltproject.org/.
