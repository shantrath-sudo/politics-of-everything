import json
from pathlib import Path

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
    project_dir = data / "projects" / project_id
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



def test_start_pilot_creates_preapproved_project_from_reliable_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(channel_cli, "ROOT", tmp_path)
    monkeypatch.setattr(channel_cli, "DATA", tmp_path / "data" / "channel")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "pilot-topic.toml").write_text("""title = "Who Really Controls a Democracy?"
candidate_id = "pilot-democracy"
summary = "An evidence-led documentary about democratic power."
research_queries = ["democracy institutions", "India parliament accountability"]
core_topic_terms = ["democracy", "parliament"]\nmechanism_terms = ["accountability", "power"]
max_sources = 6
minimum_reliable_domains = 2
""")
    candidates = [
        TopicCandidate(
            candidate_id="lead111",
            title="Democracy and institutional checks",
            summary="A report on democratic institutions and power.",
            url="https://www.reuters.com/world/example",
            article_urls=[
                "https://www.reuters.com/world/example",
                "https://www.bbc.com/news/example",
            ],
            publishers=["Reuters", "BBC"],
            topic_fit=4.0,
            india_relevance=3.0,
            international_relevance=4.0,
            score=4.2,
        ),
        TopicCandidate(
            candidate_id="lead222",
            title="India parliament accountability",
            summary="How Parliament and courts shape public power.",
            url="https://prsindia.org/example",
            article_urls=["https://prsindia.org/example"],
            publishers=["PRS Legislative Research"],
            topic_fit=4.5,
            india_relevance=5.0,
            international_relevance=3.0,
            score=4.5,
        ),
    ]
    monkeypatch.setattr(
        channel_cli,
        "scout_topics",
        lambda *, queries, limit, diagnostics=None: candidates,
    )

    result = CliRunner().invoke(channel_cli.app, ["start-pilot"])
    assert result.exit_code == 0, result.output
    assert "Pre-approved pilot topic created" in result.output
    record = WorkflowStore(channel_cli.DATA / "projects").list()[0]
    assert record["stage"] == "topic_approved"
    assert record["topic"]["title"] == "Who Really Controls a Democracy?"
    assert len(record["topic"]["article_urls"]) == 3
    assert len(record["topic"]["publishers"]) == 3

    repeated = CliRunner().invoke(channel_cli.app, ["start-pilot"])
    assert repeated.exit_code == 0, repeated.output
    assert "already exists" in repeated.output
