from datetime import datetime, timezone
import json

from ai_video_factory.channel_scout import score_topic, scout_topics, write_scout_report
from ai_video_factory.research import TrendingTopic
from ai_video_factory.scheduler import TopicLedger


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _topic(title, description="A political economy story", hours_ago=2):
    from datetime import timedelta
    return TrendingTopic(
        title=title,
        description=description,
        source="google_news",
        url="https://news.example/story",
        timestamp=NOW - timedelta(hours=hours_ago),
        volume=None,
    )


def test_score_topic_accepts_channel_relevant_india_story():
    scored = score_topic(_topic(
        "India election reforms and parliamentary democracy",
        "How India's institutions shape political power",
    ), now=NOW)
    assert scored is not None
    assert scored.india_relevance > 0
    assert "institutions_and_democracy" in scored.topic_areas
    assert scored.status == "lead_only_not_fact_checked"


def test_score_topic_rejects_off_scope_story():
    assert score_topic(_topic("New telescope discovers distant planet", "Astronomy update")) is None


def test_scout_topics_deduplicates_and_skips_previously_covered(tmp_path):
    ledger = TopicLedger(tmp_path / "topics.jsonl")
    ledger.add("politics-of-everything", "India election reforms and parliamentary democracy")
    candidates = [
        _topic("India election reforms and parliamentary democracy"),
        _topic("Global trade tariffs reshape economic power"),
        _topic("Global trade tariffs reshape economic power"),
    ]
    results = scout_topics(limit=10, now=NOW, topics=candidates, topic_ledger=ledger)
    assert len(results) == 1
    assert results[0].title == "Global trade tariffs reshape economic power"


def test_write_scout_report_is_explicitly_unapproved(tmp_path):
    candidate = score_topic(_topic("Global trade tariffs reshape economic power"), now=NOW)
    path = write_scout_report([candidate], tmp_path / "scout.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["editorial_status"] == "unapproved_leads"
    assert data["topics"][0]["status"] == "lead_only_not_fact_checked"
