# Production Plan — Fixed Operating Specification

## Output
One English documentary every Sunday, 10–15 minutes, professional documentary motion-graphics style. International audience; special focus on India. Non-partisan, evidence-led, accessible and intellectually rigorous.

## Automated local schedule (Asia/Kolkata)
- Daily at 08:00: collect and score topic leads from public RSS sources; save a dated shortlist.
- Every 4 hours: inspect project state and run only the next eligible non-approval stage.
- Every Sunday at 09:00: assemble the final_pending MP4, research dossier, script, captions, attribution and production manifest into a private local review package. This is delivery for human review, not publishing.
- When research or script generation is due: start the configured local inference model if it is not already resident; unload it after the run only if this controller started it.
- If a stage fails, preserve the previous state, log the blocker and retry on a later run.
- Never cross topic, script or final-video approval gates automatically.
- macOS launchd runs only while the user session is available; missed calendar jobs are resumed when the Mac wakes.

## Weekly editorial schedule
- Monday: review shortlist; select one topic and approve the central question.
- Tuesday: complete research dossier and source collection.
- Wednesday: create script and claim ledger; run fact-check.
- Thursday: review and approve script/storyboard.
- Friday: narration, visual acquisition and original motion graphics.
- Saturday: render, captions, audio mix and technical/editorial QA.
- Sunday: final MP4 and complete package delivered for human approval.

If a gate is blocked, pause and report the blocker. Never skip a gate or use fabricated filler to meet the calendar.

## Daily scouting
Collect international and India-relevant signals from public news/RSS sources, primary institutions, research releases and evergreen questions. Resolve RSS redirects to original HTTPS publisher articles; discard links that cannot be safely resolved. Cluster duplicates. Score each idea for channel relevance, evidence/source availability, originality signals, international relevance, India relevance where substantive, visual/story potential, feasibility for 10–15 minutes, and recency/public interest. Scores prioritise investigation; they do not establish truth or grant editorial approval. Maintain a topic ledger and record final approved topics to avoid repeats.

## Research and writing
Require at least two distinct publisher domains. Fetch actual source content through the secure transport, extract claims with verbatim evidence, record sources/claims/contradictions/verified facts, and preserve content hashes. If independent corroboration is insufficient, stop. Produce the research dossier and claim ledger before scripting. Runtime estimate uses measured narration and final render, not word count alone. High-stakes or rapidly changing subjects require stronger verification and an explicit date cutoff.

## Production
Use existing Remotion and FFmpeg. Prefer properly licensed real footage, public-domain assets with documented status, maps, data visualisations, timelines, typography and reusable original motion graphics. Synthetic assets are supplementary. Avoid large generative-video weights. Use local narration where quality is acceptable. Paid services require explicit approval.

## Quality gates
Research/source coverage; claim traceability; factual accuracy and counterarguments; runtime 10–15 minutes; clear narration and clean audio; correct resolution/aspect ratio; no black/frozen frames; visual relevance and legibility; asset licence manifest; captions, chapters, title, description and thumbnail accuracy; final human review.

## Safety and control
No automatic YouTube authentication, upload, scheduling or publication. Stop at a private local approval package. Topic and script approvals precede final production; final approval precedes any publishing action.
