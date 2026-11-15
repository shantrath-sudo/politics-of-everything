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



def test_publisher_domain_collapses_common_subdomains():
    assert channel_cli._publisher_domain("https://www.reuters.com/world/story") == "reuters.com"
    assert channel_cli._publisher_domain("https://m.bbc.co.uk/news/story") == "bbc"
    assert channel_cli._publisher_domain("https://bbc.com/news/story") == "bbc"
    assert channel_cli._publisher_domain("https://example.org/story") == "example.org"



def test_model_check_loads_calls_local_model_and_unloads(tmp_path, monkeypatch):
    class FakeSession:
        stopped = False

        def start(self):
            return "poe-qwen35-4b"

        def stop(self):
            self.stopped = True

    session = FakeSession()
    monkeypatch.setattr(channel_cli, "_new_inference_session", lambda: session)
    from ai_video_factory import longform
    monkeypatch.setattr(
        longform,
        "_lm_studio_chat",
        lambda messages, max_tokens, model: "READY",
    )
    result = CliRunner().invoke(channel_cli.app, ["model-check"])
    assert result.exit_code == 0, result.output
    assert "Local model smoke test passed" in result.output
    assert session.stopped is True
