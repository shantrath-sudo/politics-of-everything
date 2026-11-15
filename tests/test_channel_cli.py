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
    script_markdown = project_dir / "script.md"
    script_markdown.write_text("# Readable script")
    store.attach_artifact(project_id, "script_markdown", script_markdown)
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
    assert "Readable script" in result.output
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



def test_script_markdown_renderer_creates_readable_chapters_and_sources():
    payload = {
        "title": "Who Really Controls a Democracy?",
        "topic": "Democratic institutions and power",
        "description": "An evidence-led documentary.",
        "estimated_minutes": 12.5,
        "target_minutes": 12.5,
        "total_words": 1875,
        "beats": [{
            "key": "opening",
            "label": "The question of power",
            "words": 100,
            "scenes": [{
                "title": "The ballot box",
                "narration": "Elections choose representatives, but do not explain every source of power.",
                "visual_direction": "A parliamentary chamber and a simple institutional diagram.",
                "lower_third": "Who holds power?",
            }],
        }],
        "sources": ["https://www.idea.int/example", "https://prsindia.org/example"],
    }
    markdown = channel_cli._render_script_markdown(json.dumps(payload))
    assert "# Who Really Controls a Democracy?" in markdown
    assert "## The question of power" in markdown
    assert "The ballot box" in markdown
    assert "Visual direction" in markdown
    assert "https://www.idea.int/example" in markdown



def test_submit_script_creates_readable_markdown_companion(tmp_path, monkeypatch):
    monkeypatch.setattr(channel_cli, "DATA", tmp_path / "data")
    project_id = "poe-20261115-manual1"
    store = WorkflowStore(channel_cli.DATA / "projects")
    candidate = TopicCandidate(
        candidate_id="manual1",
        title="Manual documentary script",
        summary="A test script.",
        url="https://www.idea.int/example",
    )
    store.create(project_id, candidate)
    store.transition(project_id, "topic_approved")
    store.transition(project_id, "research_ready", artifact="/tmp/research.md")
    source = tmp_path / "manual-script.json"
    source.write_text(json.dumps({
        "title": "Manual documentary script",
        "topic": "Power",
        "description": "Test",
        "estimated_minutes": 12,
        "target_minutes": 12,
        "total_words": 100,
        "beats": [{
            "label": "Opening",
            "words": 100,
            "scenes": [{"title": "The question", "narration": "Who decides?"}],
        }],
        "sources": ["https://www.idea.int/example"],
    }))
    result = CliRunner().invoke(channel_cli.app, ["submit-script", project_id, str(source)])
    assert result.exit_code == 0, result.output
    record = store.get(project_id)
    markdown = Path(record["artifacts"]["script_markdown"])
    assert markdown.is_file()
    assert "# Manual documentary script" in markdown.read_text()


def test_script_approval_requires_json_and_markdown_companions(tmp_path, monkeypatch):
    monkeypatch.setattr(channel_cli, "DATA", tmp_path / "data")
    project_id = "poe-20261115-script1"
    store = WorkflowStore(channel_cli.DATA / "projects")
    candidate = TopicCandidate(
        candidate_id="script1",
        title="Script approval test",
        summary="A test script.",
        url="https://www.idea.int/example",
    )
    store.create(project_id, candidate)
    store.transition(project_id, "topic_approved")
    store.transition(project_id, "research_ready", artifact="/tmp/research.md")
    script = tmp_path / "script.json"
    script.write_text('{"beats": []}')
    store.transition(project_id, "script_pending", artifact=str(script))

    blocked = CliRunner().invoke(channel_cli.app, ["approve-script", project_id])
    assert blocked.exit_code == 2
    assert "readable Markdown script files" in blocked.output

    markdown = tmp_path / "script.md"
    markdown.write_text("# Readable script")
    store.attach_artifact(project_id, "script_markdown", markdown)
    approved = CliRunner().invoke(channel_cli.app, ["approve-script", project_id])
    assert approved.exit_code == 0, approved.output
    assert store.get(project_id)["stage"] == "script_approved"
