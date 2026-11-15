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

The politics-channel command uses public Google News RSS search feeds. It requires no API key and makes no paid API calls.

    politics-channel scout
    politics-channel status

The scout saves a dated shortlist under data/channel/scouting/. Discovery scores are prioritisation signals only; they are not fact checks. A candidate becomes a project only after explicit topic approval:

    politics-channel approve-topic CANDIDATE_ID

The project workflow then enforces this order:

1. Topic approval
2. Research dossier recorded
3. Script submitted and approved
4. Production and QA manifest recorded
5. Final MP4 submitted and approved

The final approval command only records editorial approval. It does not upload or publish.

### Production engine

The existing Remotion, FFmpeg, research, narration and quality-control components are retained as the production foundation. The long-form script engine and format presets are configured for 10–15 minute documentaries. Local inference defaults are sized more conservatively for a 16 GB Apple Silicon Mac; the selected model still needs to be installed and smoke-tested locally.

## Safety

- The legacy scheduler run YouTube uploader is disabled for this channel.
- No YouTube credentials are required for topic scouting.
- No paid service or hosted inference provider is activated by default.
- No large generative-video model weights should be downloaded.
- No topic, script or final video is automatically approved.
- No public upload or publishing occurs.

## Development

Requires Python 3.12 and the project's existing uv/FFmpeg/Remotion prerequisites. The repository CI runs the channel-critical tests on pushes to channel/bootstrap.

See docs/IMPLEMENTATION_TRACKER.md for verified progress and outstanding work.
