"""Command-line interface for Politics of Everything local operations."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

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


@app.command()
def scout(
    limit: int = typer.Option(20, min=1, max=100, help="Maximum candidates in the report"),
    report_date: str = typer.Option(None, "--date", help="Report date YYYY-MM-DD (default: today)"),
) -> None:
    """Discover political, economic, international and India-relevant topic leads."""
    try:
        selected_date = date.fromisoformat(report_date) if report_date else date.today()
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
