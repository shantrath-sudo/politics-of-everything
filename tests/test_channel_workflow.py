from datetime import UTC, datetime
from pathlib import Path

import pytest
import json

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


@pytest.fixture(autouse=True)
def _stub_host_safety_dns(monkeypatch):
    # Unit tests use reserved example domains; exercise URL policy without DNS.
    monkeypatch.setattr(
        "ai_video_factory.research_pipeline._is_blocked_host",
        lambda hostname: hostname in {"127.0.0.1", "localhost"},
    )


def _discovery_transport(url):
    if "api.gdeltproject.org" in url:
        return json.dumps({"articles": [
            {"title": "Who controls democracy? The power of institutions", "url": "https://publisher-one.example/one", "seendate": "20261114100000", "domain": "publisher-one.example"},
            {"title": "Who controls democracy? Institutions and power", "url": "https://publisher-two.example/two", "seendate": "20261114110000", "domain": "publisher-two.example"},
        ]})
    return RSS


def test_scout_clusters_related_headlines_and_scores_sources():
    candidates = scout_topics(
        queries=["democracy"],
        transport=_discovery_transport,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        resolver=lambda url: url,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title.startswith("Who controls democracy")
    assert len(candidate.publishers) >= 6
    assert candidate.source_diversity == 5.0
    assert 0 <= candidate.score <= 5


def test_scout_excludes_previously_covered_topics(tmp_path):
    ledger_path = tmp_path / "topics.jsonl"
    ledger = TopicLedger(ledger_path)
    ledger.add("politics-of-everything", "Who controls democracy? The power of institutions")
    candidates = scout_topics(
        queries=["democracy"],
        transport=_discovery_transport,
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


def test_discovery_rejects_non_https_and_credentialed_article_links():
    from ai_video_factory.channel_workflow import _valid_publisher_url

    assert not _valid_publisher_url("http://example.com/story")
    assert not _valid_publisher_url("https://user:password@example.com/story")
    assert _valid_publisher_url("https://publisher.example/story")



def test_scout_queries_both_india_and_international_editions():
    requested = []
    candidates = scout_topics(
        queries=["political power"],
        transport=lambda url: requested.append(url) or (_discovery_transport(url)),
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        resolver=lambda url: url,
    )
    assert candidates
    assert any("api.gdeltproject.org/api/v2/doc/doc" in url for url in requested)
    assert any("feeds.bbci.co.uk" in url for url in requested)
    assert not any("news.google.com" in url for url in requested)

def test_scout_reports_feed_and_article_resolution_diagnostics():
    diagnostics = {}

    def failed_resolver(url):
        raise TimeoutError(f"simulated timeout for {url}")

    candidates = scout_topics(
        queries=["democracy"],
        transport=_discovery_transport,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        resolver=failed_resolver,
        diagnostics=diagnostics,
    )

    assert candidates
    assert diagnostics["rss_headlines"] >= 12
    assert diagnostics["clusters_before_ledger"] >= 1
    assert diagnostics["clusters_after_ledger"] >= 1
    assert diagnostics["resolver_attempts"] == 0
    assert diagnostics["resolver_failures"] == 0
    assert diagnostics["resolved_candidates"] > 0
    assert diagnostics["resolver_failure_samples"] == []





def test_gdelt_doc_parses_direct_article_urls_and_24_hour_window(monkeypatch):
    import json
    import urllib.parse
    import ai_video_factory.channel_workflow as workflow

    monkeypatch.setattr(workflow, "DEFAULT_PUBLISHER_FEEDS", ())
    requested = []
    payload = {"articles": [{
        "title": "Democracy institutions and political power",
        "url": "https://publisher.example/story",
        "seendate": "20261117103000",
        "domain": "publisher.example",
    }]}
    def transport(url):
        requested.append(url)
        return json.dumps(payload)

    candidates = workflow.scout_topics(queries=["democracy power"], transport=transport)
    assert len(candidates) == 1
    assert candidates[0].url == "https://publisher.example/story"
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(requested[0]).query)
    assert params["timespan"] == ["24h"]
    assert params["format"] == ["json"]
    assert params["mode"] == ["ArtList"]


def test_gdelt_rejects_non_https_and_private_article_urls(monkeypatch):
    import json
    import ai_video_factory.channel_workflow as workflow

    monkeypatch.setattr(workflow, "DEFAULT_PUBLISHER_FEEDS", ())
    payload = {"articles": [
        {"title": "Democracy power institutions", "url": "http://publisher.example/story"},
        {"title": "Democracy power institutions", "url": "https://127.0.0.1/private"},
    ]}
    candidates = workflow.scout_topics(
        queries=["democracy"], transport=lambda _url: json.dumps(payload)
    )
    assert candidates == []


def test_publisher_rss_is_used_when_gdelt_fails(monkeypatch):
    import ai_video_factory.channel_workflow as workflow

    monkeypatch.setattr(
        workflow, "DEFAULT_PUBLISHER_FEEDS",
        (("Publisher One", "https://publisher.example/rss"),),
    )
    diagnostics = {}
    def transport(url):
        if "publisher.example/rss" in url:
            return RSS
        raise TimeoutError("GDELT offline")

    candidates = workflow.scout_topics(
        queries=["democracy"], transport=transport, diagnostics=diagnostics
    )
    assert candidates
    assert "Publisher One" in candidates[0].publishers
    assert diagnostics["feed_failures"] == 1
    assert diagnostics["providers"] == ["GDELT DOC", "direct publisher RSS"]


def test_scout_penalises_lifestyle_noise_without_rejecting_political_stories():
    from ai_video_factory.channel_workflow import _score_candidate

    now = datetime(2026, 11, 17, 12, tzinfo=UTC)
    noise = TopicCandidate(
        candidate_id="noise01",
        title="Basketball star announces travel plans after tournament",
        summary="",
        url="https://publisher.example/noise",
        publishers=["Publisher One"],
        published_at="Tue, 17 Nov 2026 11:00:00 GMT",
    )
    politics = TopicCandidate(
        candidate_id="policy01",
        title="Court ruling reshapes government surveillance policy",
        summary="A constitutional rights dispute over state power",
        url="https://publisher.example/policy",
        publishers=["Publisher One"],
        published_at="Tue, 17 Nov 2026 11:00:00 GMT",
    )
    _score_candidate(noise, now)
    _score_candidate(politics, now)
    assert politics.score > noise.score


def test_scout_reports_headline_counts_by_provider():
    diagnostics = {}
    candidates = scout_topics(
        queries=["democracy"],
        transport=_discovery_transport,
        now=datetime(2026, 11, 15, 12, tzinfo=UTC),
        limit=10,
        diagnostics=diagnostics,
    )
    assert candidates
    assert diagnostics["headlines_received"] == diagnostics["rss_headlines"]
    assert diagnostics["provider_headline_counts"]["GDELT DOC"] == 2
    assert diagnostics["provider_headline_counts"]["BBC India"] == 2


def test_gdelt_retries_rate_limit_once_with_bounded_delay(monkeypatch):
    import json
    import urllib.error
    import ai_video_factory.channel_workflow as workflow

    monkeypatch.setattr(workflow, "DEFAULT_PUBLISHER_FEEDS", ())
    delays = []
    monkeypatch.setattr(workflow.time, "sleep", delays.append)
    calls = []

    def transport(url):
        calls.append(url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                url, 429, "Too Many Requests", {"Retry-After": "2"}, None
            )
        return json.dumps({"articles": [{
            "title": "Court ruling reshapes government policy",
            "url": "https://publisher.example/story",
            "seendate": "20261117103000",
            "domain": "publisher.example",
        }]})

    candidates = workflow.scout_topics(
        queries=["democracy"], transport=transport
    )
    assert len(candidates) == 1
    assert len(calls) == 2
    assert delays == [5.0]


def test_gdelt_retries_transient_non_json_response_once(monkeypatch):
    import json
    import ai_video_factory.channel_workflow as workflow

    monkeypatch.setattr(workflow, "DEFAULT_PUBLISHER_FEEDS", ())
    delays = []
    monkeypatch.setattr(workflow.time, "sleep", delays.append)
    calls = []

    def transport(url):
        calls.append(url)
        if len(calls) == 1:
            return "<html>temporary upstream response</html>"
        return json.dumps({"articles": [{
            "title": "Constitutional court reviews government policy",
            "url": "https://publisher.example/story",
            "seendate": "20261117103000",
            "domain": "publisher.example",
        }]})

    candidates = workflow.scout_topics(
        queries=["democracy"], transport=transport
    )
    assert len(candidates) == 1
    assert len(calls) == 2
    assert delays == [5.0]



def test_scout_penalises_incidental_state_or_minister_mentions_in_noise():
    from ai_video_factory.channel_workflow import _score_candidate

    now = datetime(2026, 11, 17, 12, tzinfo=UTC)
    basketball = TopicCandidate(
        candidate_id="basket01",
        title="Basketball player arrested at Nigerian airport",
        summary="The player is from the state of Georgia.",
        url="https://publisher.example/basketball",
        publishers=["Publisher One"],
        published_at="Tue, 17 Nov 2026 11:00:00 GMT",
    )
    cricket = TopicCandidate(
        candidate_id="crick01",
        title="Prince and Princess play street cricket in Mumbai",
        summary="They met locals ahead of a meeting with the Indian Prime Minister.",
        url="https://publisher.example/cricket",
        publishers=["Publisher One"],
        published_at="Tue, 17 Nov 2026 11:00:00 GMT",
    )
    labor = TopicCandidate(
        candidate_id="labor01",
        title="Labor leader honored for civil rights and union organizing",
        summary="Her advocacy changed labor protections and public policy.",
        url="https://publisher.example/labor",
        publishers=["Publisher One"],
        published_at="Tue, 17 Nov 2026 11:00:00 GMT",
    )
    for candidate in (basketball, cricket, labor):
        _score_candidate(candidate, now)

    assert basketball.score < labor.score
    assert cricket.score < labor.score
