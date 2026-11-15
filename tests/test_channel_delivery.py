import json
from pathlib import Path
import plistlib

from ai_video_factory import channel_cli
from ai_video_factory.channel_workflow import TopicCandidate, WorkflowStore


def test_delivery_package_is_private_and_does_not_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(channel_cli, "DATA", tmp_path)
    project_id = "poe-20261115-abc123"
    project_dir = tmp_path / "projects" / project_id
    research_dir = project_dir / "research"
    research_dir.mkdir(parents=True)

    dossier = research_dir / "research_brief.md"
    dossier.write_text("Verified research notes.")
    script = project_dir / "script.json"
    script.write_text('{"title":"Who controls democracy?"}')
    video = project_dir / "final.mp4"
    video.write_bytes(b"fake-mp4")
    attribution = project_dir / "attribution.json"
    attribution.write_text('{"assets":[]}')
    subtitles = project_dir / "captions.srt"
    subtitles.write_text("1\n00:00:00,000 --> 00:00:01,000\nIntro\n")

    manifest = project_dir / "production_manifest.json"
    manifest.write_text(json.dumps({
        "artifacts": {
            "master": str(video),
            "attribution": str(attribution),
            "subtitles": str(subtitles),
        }
    }))

    store = WorkflowStore(tmp_path / "projects")
    candidate = TopicCandidate(
        candidate_id="abc123",
        title="Who controls democracy?",
        summary="A documentary about institutions and power.",
        url="https://example.org/article",
    )
    store.create(project_id, candidate)
    store.transition(project_id, "topic_approved")
    store.transition(project_id, "research_ready", artifact=str(dossier))
    store.transition(project_id, "script_pending", artifact=str(script))
    store.transition(project_id, "script_approved")
    store.transition(project_id, "production_ready", artifact=str(manifest))
    store.transition(project_id, "final_pending", artifact=str(video))

    channel_cli.deliver(force=True)

    deliveries = tmp_path / "deliveries"
    package_dirs = list(deliveries.rglob("delivery_manifest.json"))
    assert len(package_dirs) == 1
    package = package_dirs[0].parent
    assert (package / "final.mp4").read_bytes() == b"fake-mp4"
    assert (package / "script.json").is_file()
    assert (package / "research" / "research_brief.md").is_file()
    assert (package / "attribution.json").is_file()
    assert (package / "captions.srt").is_file()
    delivery = json.loads((package / "delivery_manifest.json").read_text())
    assert delivery["final_approval_required"] is True
    assert delivery["published"] is False
    assert "No YouTube upload or publication" in (package / "REVIEW.md").read_text()
    record = store.get(project_id)
    assert record["artifacts"]["delivery_package"] == str(package)
    assert record["artifacts"]["delivery_manifest"] == str(package / "delivery_manifest.json")


def test_launchd_templates_define_daily_advance_and_sunday_delivery():
    root = Path(__file__).resolve().parents[1] / "launchd"
    scout = plistlib.loads((root / "com.politics-of-everything.scout.plist.template").read_bytes())
    advance = plistlib.loads((root / "com.politics-of-everything.advance.plist.template").read_bytes())
    delivery = plistlib.loads((root / "com.politics-of-everything.delivery.plist.template").read_bytes())
    assert scout["StartCalendarInterval"] == {"Hour": 8, "Minute": 0}
    assert advance["StartInterval"] == 14_400
    assert delivery["StartCalendarInterval"] == {"Weekday": 0, "Hour": 9, "Minute": 0}



def test_final_approval_is_blocked_until_private_package_exists(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    monkeypatch.setattr(channel_cli, "DATA", tmp_path)
    project_id = "poe-20261115-approve1"
    project_dir = tmp_path / "projects" / project_id
    project_dir.mkdir(parents=True)
    video = project_dir / "final.mp4"
    video.write_bytes(b"fake-mp4")

    store = WorkflowStore(tmp_path / "projects")
    candidate = TopicCandidate(
        candidate_id="approve1",
        title="Who controls democracy?",
        summary="A documentary about institutions and power.",
        url="https://www.idea.int/example",
    )
    store.create(project_id, candidate)
    store.transition(project_id, "topic_approved")
    store.transition(project_id, "research_ready", artifact=str(project_dir / "research.md"))
    store.transition(project_id, "script_pending", artifact=str(project_dir / "script.json"))
    store.transition(project_id, "script_approved")
    store.transition(project_id, "production_ready", artifact=str(project_dir / "manifest.json"))
    store.transition(project_id, "final_pending", artifact=str(video))

    runner = CliRunner()
    blocked = runner.invoke(channel_cli.app, ["approve-final", project_id])
    assert blocked.exit_code == 2
    assert "only after the private Sunday review package" in blocked.output
    assert store.get(project_id)["stage"] == "final_pending"

    package = tmp_path / "deliveries" / project_id
    package.mkdir(parents=True)
    delivery_manifest = package / "delivery_manifest.json"
    delivery_manifest.write_text('{"published": false}')
    store.record_delivery(project_id, package, delivery_manifest)

    approved = runner.invoke(channel_cli.app, ["approve-final", project_id])
    assert approved.exit_code == 0, approved.output
    assert "No YouTube upload or publication" in approved.output
    assert store.get(project_id)["stage"] == "final_approved"
