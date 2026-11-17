from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_video_factory.channel_workflow import (
    ChannelWorkflowError,
    TopicCandidate,
    WorkflowStore,
    save_scout_report,
    scout_topics,
)
from ai_video_factory.scheduler import TopicLedger


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
<title>Who controls democracy? The power of institutions</title>
<link>https://news.example/one</link>
<description>How institutions shape political power.</description>
<pubDate>Sat, 14 Nov 2026 10:00:00 GMT</pubDate>
<source url="https://publisher-one.example">Publisher One</source>
</item>
<item>
<title>Who controls democracy? Institutions and power</title>
<link>https://news.example/two</link>
<description>Democratic accountability and political institutions.</description>
<pubDate>Sat, 14 Nov 2026 11:00:00 GMT</pubDate>
<source url="https://publisher-two.example">Publisher Two</source>
</item>
</channel></rss>"""


def test_scout_clusters_related_headlines_and_scores_sources():
    candidates = scout_topics(
        queries=["democracy"],
        transport=lambda _url: RSS,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        resolver=lambda url: url,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title.startswith("Who controls democracy")
    assert len(candidate.publishers) == 2
    assert candidate.source_diversity == 3.0
    assert 0 <= candidate.score <= 5


def test_scout_excludes_previously_covered_topics(tmp_path):
    ledger_path = tmp_path / "topics.jsonl"
    ledger = TopicLedger(ledger_path)
    ledger.add("politics-of-everything", "Who controls democracy? The power of institutions")
    candidates = scout_topics(
        queries=["democracy"],
        transport=lambda _url: RSS,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        ledger_path=ledger_path,
        resolver=lambda url: url,
    )
    assert candidates == []


def test_scout_report_is_saved_with_discovery_disclaimer(tmp_path):
    candidate = TopicCandidate(
        candidate_id="abc123",
        title="Who controls democracy?",
        summary="",
        url="https://example.org",
    )
    path = save_scout_report([candidate], tmp_path, on_date=datetime(2026, 11, 15).date())
    payload = __import__("json").loads(path.read_text())
    assert payload["candidate_count"] == 1
    assert "not verified facts" in payload["disclaimer"]
    markdown = path.with_suffix(".md").read_text()
    assert "Who controls democracy?" in markdown
    assert "Candidate ID" in markdown
    assert "--date 2026-11-15" in markdown
    assert "politics-channel approve-topic abc123 --date 2026-11-15" in markdown


def test_workflow_requires_explicit_order_and_artifacts(tmp_path):
    store = WorkflowStore(tmp_path)
    candidate = TopicCandidate(
        candidate_id="abc123",
        title="Who controls democracy?",
        summary="A study of democratic institutions.",
        url="https://example.org",
    )
    store.create("poe-20261115-abc123", candidate)
    with pytest.raises(ChannelWorkflowError, match="invalid workflow transition"):
        store.transition("poe-20261115-abc123", "script_approved")

    store.transition("poe-20261115-abc123", "topic_approved")
    with pytest.raises(ChannelWorkflowError, match="invalid workflow transition"):
        store.transition("poe-20261115-abc123", "script_pending")
    store.transition("poe-20261115-abc123", "research_ready", artifact="/tmp/research.md")
    store.transition("poe-20261115-abc123", "script_pending", artifact="/tmp/script.md")
    approved = store.transition("poe-20261115-abc123", "script_approved")
    assert approved["approvals"]["script"] is True
    with pytest.raises(ChannelWorkflowError, match="invalid workflow transition"):
        store.transition("poe-20261115-abc123", "final_approved")


def test_workflow_requires_final_video_before_final_approval(tmp_path):
    store = WorkflowStore(tmp_path)
    candidate = TopicCandidate(
        candidate_id="abc123",
        title="Who controls democracy?",
        summary="",
        url="https://example.org",
    )
    project = "poe-20261115-abc123"
    store.create(project, candidate)
    store.transition(project, "topic_approved")
    store.transition(project, "research_ready", artifact="/tmp/research.md")
    store.transition(project, "script_pending", artifact="/tmp/script.md")
    store.transition(project, "script_approved")
    store.transition(project, "production_ready", artifact="/tmp/manifest.json")
    store.transition(project, "final_pending", artifact="/tmp/final.mp4")
    record = store.transition(project, "final_approved")
    assert record["stage"] == "final_approved"
    assert record["approvals"] == {"topic": True, "script": True, "final": True}


def test_article_resolver_rejects_non_https_links_without_network():
    from ai_video_factory.channel_workflow import ChannelWorkflowError, _resolve_article_url

    with pytest.raises(ChannelWorkflowError, match="HTTPS"):
        _resolve_article_url("http://example.com/story")
    with pytest.raises(ChannelWorkflowError, match="HTTPS"):
        _resolve_article_url("https://user:password@example.com/story")



def test_scout_queries_both_india_and_international_editions():
    requested = []
    candidates = scout_topics(
        queries=["political power"],
        transport=lambda url: requested.append(url) or RSS,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        resolver=lambda url: url,
    )
    assert candidates
    assert any("hl=en-IN" in url and "gl=IN" in url for url in requested)
    assert any("hl=en-GB" in url and "gl=GB" in url for url in requested)
    assert any("hl=en-US" in url and "gl=US" in url for url in requested)

def test_scout_reports_feed_and_article_resolution_diagnostics():
    diagnostics = {}

    def failed_resolver(url):
        raise TimeoutError(f"simulated timeout for {url}")

    candidates = scout_topics(
        queries=["democracy"],
        transport=lambda _url: RSS,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        resolver=failed_resolver,
        diagnostics=diagnostics,
    )

    assert candidates == []
    assert diagnostics["rss_headlines"] == 6
    assert diagnostics["clusters_before_ledger"] == 1
    assert diagnostics["clusters_after_ledger"] == 1
    assert diagnostics["resolver_attempts"] == 2
    assert diagnostics["resolver_failures"] == 2
    assert diagnostics["resolved_candidates"] == 0
    assert diagnostics["resolver_failure_samples"]

