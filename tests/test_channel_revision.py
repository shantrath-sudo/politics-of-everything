import pytest

from ai_video_factory.channel_workflow import ChannelWorkflowError, TopicCandidate, WorkflowStore


def _candidate():
    return TopicCandidate(
        candidate_id="rev123456",
        title="Who Really Controls a Democracy?",
        summary="An evidence-led documentary on institutional power.",
        url="https://www.idea.int/example",
        article_urls=["https://www.idea.int/example", "https://prsindia.org/example"],
    )


def _script_pending_store(tmp_path):
    store = WorkflowStore(tmp_path / "projects")
    project_id = "poe-20261115-rev123456"
    store.create(project_id, _candidate())
    store.transition(project_id, "topic_approved")
    store.transition(project_id, "research_ready", artifact="/tmp/research-brief.md")
    store.transition(project_id, "script_pending", artifact="/tmp/script.json")
    return store, project_id


def test_script_rejection_reopens_research_and_preserves_old_script(tmp_path):
    store, project_id = _script_pending_store(tmp_path)
    record = store.request_revision(project_id, "Clarify the role of courts and add a stronger counterargument.")
    assert record["stage"] == "research_ready"
    assert record["revision_count"] == 1
    assert record["pending_revision_feedback"].startswith("Clarify the role")
    assert record["artifacts"]["script"] == "/tmp/script.json"
    assert record["approvals"]["script"] is False
    assert record["approvals"]["final"] is False
    assert record["history"][-1]["event"] == "revision_requested"


def test_final_video_rejection_reopens_script_and_invalidates_old_render(tmp_path):
    store, project_id = _script_pending_store(tmp_path)
    store.transition(project_id, "script_approved")
    store.transition(project_id, "production_ready", artifact="/tmp/production-manifest.json")
    store.transition(project_id, "final_pending", artifact="/tmp/final.mp4")
    record = store.request_revision(project_id, "The visual explanation of lobbying needs clearer examples.")
    assert record["stage"] == "research_ready"
    assert "production_manifest" not in record["artifacts"]
    assert "final_video" not in record["artifacts"]
    assert record["revision_count"] == 1
    previous = record["revision_requests"][0]["previous_artifacts"]
    assert previous["final_video"] == "/tmp/final.mp4"
    assert previous["production_manifest"] == "/tmp/production-manifest.json"


def test_revision_requires_feedback_and_an_approval_stage(tmp_path):
    store = WorkflowStore(tmp_path / "projects")
    project_id = "poe-20261115-rev123456"
    store.create(project_id, _candidate())
    with pytest.raises(ChannelWorkflowError, match="only be requested"):
        store.request_revision(project_id, "Please revise")
    store.transition(project_id, "topic_approved")
    store.transition(project_id, "research_ready", artifact="/tmp/research-brief.md")
    store.transition(project_id, "script_pending", artifact="/tmp/script.json")
    with pytest.raises(ChannelWorkflowError, match="cannot be empty"):
        store.request_revision(project_id, " ")
    with pytest.raises(ChannelWorkflowError, match="2000 characters"):
        store.request_revision(project_id, "x" * 2001)
