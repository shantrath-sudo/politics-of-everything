"""Command-line interface for Politics of Everything local operations."""
from __future__ import annotations

import json
import tomllib
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import typer

from ai_video_factory.scheduler import TopicLedger
from ai_video_factory.channel_workflow import (
    ChannelWorkflowError,
    TopicCandidate,
    WorkflowStore,
    scout_topics,
    save_scout_report,
)

app = typer.Typer(no_args_is_help=True, help="Politics of Everything local editorial workflow.")
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "channel"
CONFIG = ROOT / "config" / "channels.toml"


def _queries() -> list[str]:
    import tomllib
    data = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    channels = data.get("channels") or []
    if not channels:
        raise ChannelWorkflowError("channel configuration contains no channels")
    return list(channels[0].get("research_queries") or [])


def _store() -> WorkflowStore:
    return WorkflowStore(DATA / "projects")


def _project_path(value: str, suffixes: tuple[str, ...] | None = None) -> str:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise typer.BadParameter(f"file does not exist: {path}")
    if suffixes and path.suffix.lower() not in suffixes:
        raise typer.BadParameter(f"expected one of these file types: {', '.join(suffixes)}")
    return str(path)




def _today() -> date:
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def _project_dir(project_id: str) -> Path:
    return DATA / "projects" / project_id


def _research_project(project_id: str) -> dict:
    record = _store().get(project_id)
    if record["stage"] != "topic_approved":
        raise ChannelWorkflowError(f"{project_id}: research requires topic_approved, got {record['stage']}")
    candidate = record["topic"]
    urls = list(dict.fromkeys(candidate.get("article_urls") or [candidate["url"]]))
    publishers = set(candidate.get("publishers") or [])
    if len(urls) < 2 or len(publishers) < 2:
        raise ChannelWorkflowError("research requires at least two independent publisher sources")
    from ai_video_factory.research_pipeline import (
        make_production_extractor,
        make_secure_http_transport,
        run_research,
        write_research_artifacts,
        flag_sensitive_topic,
    )
    inference = tomllib.loads((ROOT / "config" / "inference.toml").read_text(encoding="utf-8"))
    endpoint = inference["base_url"].rstrip("/") + "/chat/completions"
    extractor = make_production_extractor(endpoint_url=endpoint, model_name=inference["model_key"])
    result = run_research(
        candidate["title"], urls[:8],
        production_extractor=extractor,
        content_fetcher=make_secure_http_transport(),
    )
    if not result.verified_facts:
        raise ChannelWorkflowError("research produced no independently corroborated verified facts; project remains paused")
    project_dir = _project_dir(project_id)
    research_dir = project_dir / "research"
    paths = write_research_artifacts(result, research_dir)
    reasons = flag_sensitive_topic(candidate["title"])
    metadata = {
        "topic": candidate["title"],
        "source_count": len(result.sources),
        "claim_count": len(result.claims),
        "verified_fact_count": len(result.verified_facts),
        "contradiction_count": len(result.contradictions),
        "flagged_for_human_review": result.flagged_for_review or bool(reasons),
        "review_reasons": list(dict.fromkeys([*result.flag_reasons, *reasons])),
        "extractor_model": result.extractor_model_id,
        "source_content_hashes": result.source_content_hashes,
        "output_digest": result.output_digest,
    }
    (research_dir / "editorial_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return _store().transition(project_id, "research_ready", artifact=str(paths["research_brief"]))


def _draft_project_script(project_id: str) -> dict:
    record = _store().get(project_id)
    if record["stage"] != "research_ready":
        raise ChannelWorkflowError(f"{project_id}: script drafting requires research_ready, got {record['stage']}")
    candidate = record["topic"]
    research_brief = Path(record["artifacts"]["research_dossier"]).read_text(encoding="utf-8")
    urls = list(dict.fromkeys(candidate.get("article_urls") or [candidate["url"]]))
    from ai_video_factory.longform import generate_longform_script, check_topic_adherence
    script = generate_longform_script(
        topic=candidate["title"],
        description=candidate.get("summary") or candidate["title"],
        source_url=urls[0],
        target_minutes=12.5,
        research_brief=research_brief,
        title=candidate["title"],
        sources=urls,
        format_key="systems_explainer",
        verify_source_urls=True,
    )
    check_topic_adherence(script)
    project_dir = _project_dir(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    script_path = project_dir / "script.json"
    script_path.write_text(script.to_json() + "\n", encoding="utf-8")
    return _store().transition(project_id, "script_pending", artifact=str(script_path))


def _render_project(project_id: str) -> dict:
    record = _store().get(project_id)
    if record["stage"] != "script_approved":
        raise ChannelWorkflowError(f"{project_id}: rendering requires script_approved, got {record['stage']}")
    candidate = record["topic"]
    script_path = Path(record["artifacts"]["script"])
    script_data = json.loads(script_path.read_text(encoding="utf-8"))
    from ai_video_factory.theme import resolve_theme
    from ai_video_factory.video_pipeline import VideoJob, run_video_pipeline
    project_dir = _project_dir(project_id)
    render_dir = project_dir / "render"
    job = VideoJob(
        topic=candidate["title"],
        description=candidate.get("summary") or candidate["title"],
        source_url=(candidate.get("article_urls") or [candidate["url"]])[0],
        output_path=render_dir,
        title=script_data["title"],
        duration_seconds=750,
    )
    result = run_video_pipeline(
        project_root=ROOT,
        data_root=DATA,
        job=job,
        script_path=script_path,
        theme=resolve_theme("generic"),
        longform=True,
        target_duration_minutes=12.5,
        draft=False,
    )
    if result.status != "pass":
        raise ChannelWorkflowError(f"render/quality pipeline failed: {result.error or result.metadata.get('error', 'unknown error')}")
    master = result.artifacts.get("master")
    if not master or not Path(master).is_file():
        raise ChannelWorkflowError("pipeline reported success but the master MP4 is missing")
    manifest_path = project_dir / "production_manifest.json"
    manifest = {
        "project_id": project_id,
        "topic": candidate["title"],
        "status": result.status,
        "run_id": result.run_id,
        "artifacts": result.artifacts,
        "metadata": result.metadata,
        "master_video": master,
        "created_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        "publishing": "disabled",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _store().transition(project_id, "production_ready", artifact=str(manifest_path))
    return _store().transition(project_id, "final_pending", artifact=str(Path(master).resolve()))

@app.command()
def scout(
    limit: int = typer.Option(20, min=1, max=100, help="Maximum candidates in the report"),
    report_date: str = typer.Option(None, "--date", help="Report date YYYY-MM-DD (default: today)"),
) -> None:
    """Discover political, economic, international and India-relevant topic leads."""
    try:
        selected_date = date.fromisoformat(report_date) if report_date else _today()
        candidates = scout_topics(
            queries=_queries(),
            limit=limit,
            ledger_path=DATA / "topics.jsonl",
        )
        path = save_scout_report(candidates, DATA, on_date=selected_date)
        typer.echo(f"Saved {len(candidates)} topic leads: {path}")
        for index, candidate in enumerate(candidates, 1):
            publishers = ", ".join(candidate.publishers[:3])
            typer.echo(
                f"{index:02d}. [{candidate.candidate_id}] {candidate.title} "
                f"(priority {candidate.score:.2f}/5; sources: {publishers})"
            )
        typer.echo("Discovery scores are prioritisation signals, not fact checks or approval.")
    except (ValueError, ChannelWorkflowError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("approve-topic")
def approve_topic(
    candidate_id: str = typer.Argument(..., help="Candidate ID from the latest scouting report"),
    report_date: str = typer.Option(None, "--date", help="Scouting report date YYYY-MM-DD"),
) -> None:
    """Select a topic and create a project after explicit Editor-in-Chief approval."""
    selected_date = date.fromisoformat(report_date) if report_date else date.today()
    report = DATA / "scouting" / f"{selected_date.isoformat()}.json"
    if not report.is_file():
        raise typer.BadParameter(f"scouting report not found: {report}")
    payload = json.loads(report.read_text(encoding="utf-8"))
    item = next((x for x in payload.get("candidates", []) if x.get("candidate_id") == candidate_id), None)
    if item is None:
        raise typer.BadParameter(f"candidate not found in report: {candidate_id}")
    candidate = TopicCandidate(**item)
    active = [item for item in _store().list() if item.get("stage") != "final_approved"]
    if active:
        raise typer.BadParameter(
            "There is already an active documentary project. Complete or approve its final video before selecting another topic."
        )
    project_id = f"poe-{selected_date.strftime('%Y%m%d')}-{candidate_id}"
    try:
        _store().create(project_id, candidate)
        record = _store().transition(project_id, "topic_approved")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)
    typer.echo(f"Topic approved. Project created: {project_id}")
    typer.echo(candidate.title)
    typer.echo(f"Next stage: {record['stage']}")


@app.command("research-ready")
def research_ready(
    project_id: str = typer.Argument(...),
    dossier: str = typer.Argument(..., help="Path to completed research dossier"),
) -> None:
    """Record a completed research dossier; does not imply script approval."""
    path = _project_path(dossier)
    try:
        record = _store().transition(project_id, "research_ready", artifact=path)
        typer.echo(f"{project_id}: {record['stage']}")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("submit-script")
def submit_script(
    project_id: str = typer.Argument(...),
    script: str = typer.Argument(..., help="Path to complete documentary script"),
) -> None:
    """Submit a script for human approval."""
    path = _project_path(script, (".md", ".txt", ".json"))
    try:
        record = _store().transition(project_id, "script_pending", artifact=path)
        typer.echo(f"Script submitted for review: {project_id} ({record['stage']})")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("approve-script")
def approve_script(project_id: str = typer.Argument(...)) -> None:
    """Approve a submitted script; required before rendering."""
    try:
        record = _store().transition(project_id, "script_approved")
        typer.echo(f"Script approved: {project_id}")
        typer.echo(f"Next stage: {record['stage']}")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("production-ready")
def production_ready(
    project_id: str = typer.Argument(...),
    manifest: str = typer.Argument(..., help="Path to completed production manifest"),
) -> None:
    """Record completed render and QA metadata before final review."""
    path = _project_path(manifest, (".json",))
    try:
        record = _store().transition(project_id, "production_ready", artifact=path)
        typer.echo(f"Production complete: {project_id} ({record['stage']})")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("submit-final")
def submit_final(
    project_id: str = typer.Argument(...),
    video: str = typer.Argument(..., help="Path to final MP4"),
) -> None:
    """Submit the final MP4 for Editor-in-Chief approval."""
    path = _project_path(video, (".mp4",))
    try:
        record = _store().transition(project_id, "final_pending", artifact=path)
        typer.echo(f"Final video submitted for approval: {project_id} ({record['stage']})")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("approve-final")
def approve_final(project_id: str = typer.Argument(...)) -> None:
    """Record final editorial approval. This command never publishes the video."""
    try:
        record = _store().transition(project_id, "final_approved")
        topic_ledger = TopicLedger(DATA / "topics.jsonl")
        topic_ledger.add("politics-of-everything", record["topic"]["title"], run_id=project_id)
        typer.echo(f"Final editorial approval recorded: {project_id}")
        typer.echo("No YouTube upload or publication was performed.")
        typer.echo(f"Stage: {record['stage']}")
    except ChannelWorkflowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command()
def research(project_id: str = typer.Argument(...)) -> None:
    """Run source collection and evidence-backed claim extraction for an approved topic."""
    try:
        record = _research_project(project_id)
        typer.echo(f"Research dossier complete: {project_id}")
        typer.echo(f"Stage: {record['stage']}")
        typer.echo(f"Dossier: {record['artifacts']['research_dossier']}")
    except Exception as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command("draft-script")
def draft_script(project_id: str = typer.Argument(...)) -> None:
    """Generate a sourced 10–15 minute script and submit it for human approval."""
    try:
        record = _draft_project_script(project_id)
        typer.echo(f"Script submitted for review: {project_id}")
        typer.echo(f"Script: {record['artifacts']['script']}")
    except Exception as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command()
def render(project_id: str = typer.Argument(...)) -> None:
    """Render an approved script, run QA and prepare the final review package."""
    try:
        record = _render_project(project_id)
        typer.echo(f"Final video ready for review: {project_id}")
        typer.echo(f"MP4: {record['artifacts']['final_video']}")
        typer.echo("No upload or publication was performed.")
    except Exception as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2)


@app.command()
def advance() -> None:
    """Run the next non-approval stages; stop at every human approval gate."""
    for record in _store().list():
        project_id = record["project_id"]
        try:
            stage = record["stage"]
            if stage == "topic_approved":
                record = _research_project(project_id)
                stage = record["stage"]
            if stage == "research_ready":
                record = _draft_project_script(project_id)
                stage = record["stage"]
            if stage == "script_approved":
                record = _render_project(project_id)
                stage = record["stage"]
            typer.echo(f"{project_id}: {stage}")
        except Exception as error:
            typer.echo(f"{project_id}: PAUSED — {error}", err=True)


@app.command()
def status() -> None:
    """Show current projects and the latest scouting report."""
    records = _store().list()
    if not records:
        typer.echo("No documentary projects have been selected.")
    for record in records:
        typer.echo(
            f"{record['project_id']} | {record['stage']} | "
            f"{record['topic'].get('title', 'Untitled')}"
        )
    reports = sorted((DATA / "scouting").glob("*.json")) if (DATA / "scouting").is_dir() else []
    if reports:
        latest = json.loads(reports[-1].read_text(encoding="utf-8"))
        typer.echo(f"Latest scouting report: {reports[-1].name} ({latest.get('candidate_count', 0)} candidates)")


if __name__ == "__main__":
    app()
