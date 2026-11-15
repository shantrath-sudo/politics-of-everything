import json

from typer.testing import CliRunner

from ai_video_factory import channel_cli
from ai_video_factory.channel_workflow import TopicCandidate, WorkflowStore


def test_status_shows_approval_paths_and_sensitive_review_flags(tmp_path, monkeypatch):
    data = tmp_path / "data" / "channel"
    monkeypatch.setattr(channel_cli, "ROOT", tmp_path)
    monkeypatch.setattr(channel_cli, "DATA", data)

    store = WorkflowStore(data / "projects")
    candidate = TopicCandidate(
        candidate_id="pilot123456",
        title="Who Really Controls a Democracy?",
        summary="An evidence-led examination of democratic institutions.",
        url="https://www.idea.int/example",
    )
    project_id = "poe-20261115-pilot123456"
    store.create(project_id, candidate)
    store.transition(project_id, "topic_approved")
    research_dir = data / "projects" / project_id / "research"
    research_dir.mkdir(parents=True)
    dossier = research_dir / "research_brief.md"
    dossier.write_text("# Research dossier")
    store.transition(project_id, "research_ready", artifact=str(dossier))
    script = data / "projects" / project_id / "script.json"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("{}")
    store.transition(project_id, "script_pending", artifact=str(script))
    (research_dir / "editorial_metadata.json").write_text(json.dumps({
        "flagged_for_human_review": True,
        "review_reasons": ["topic touches sensitive area: election"],
    }))

    report_dir = data / "scouting"
    report_dir.mkdir(parents=True)
    (report_dir / "2026-11-15.json").write_text(json.dumps({"candidate_count": 2}))
    (report_dir / "2026-11-15.md").write_text("# Daily shortlist")

    result = CliRunner().invoke(channel_cli.app, ["status"])
    assert result.exit_code == 0, result.output
    assert "script_pending" in result.output
    assert "Script awaiting approval" in result.output
    assert "HUMAN REVIEW REQUIRED" in result.output
    assert "topic touches sensitive area: election" in result.output
    assert "2026-11-15.md" in result.output
    assert "Publishing: disabled" in result.output
