"""Politics of Everything topic scouting.

This is a deterministic discovery and triage layer. It ranks leads; it does
not verify facts, choose the editorial position, or approve a topic.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ai_video_factory.research import TrendingTopic, get_trending_topics
from ai_video_factory.scheduler import TopicLedger


CHANNEL_TERMS: dict[str, tuple[str, ...]] = {
    "institutions_and_democracy": (
        "democracy", "election", "parliament", "congress", "constitution",
        "court", "supreme court", "government", "president", "prime minister",
        "political party", "voting", "legislature", "governance", "state power",
    ),
    "political_economy": (
        "economy", "economic", "trade", "tariff", "tax", "budget", "debt",
        "inflation", "inequality", "wealth", "billionaire", "corporate",
        "labour", "labor", "jobs", "wages", "bank", "central bank", "energy",
    ),
    "geopolitics": (
        "geopolitics", "war", "conflict", "diplomacy", "sanctions", "nato",
        "united nations", "china", "russia", "united states", "europe",
        "middle east", "border", "military", "foreign policy", "treaty",
    ),
    "society_and_ideas": (
        "society", "protest", "rights", "freedom", "movement", "ideology",
        "political thought", "identity", "religion", "culture", "migration",
        "education", "media", "public opinion", "social change",
    ),
    "technology_and_power": (
        "artificial intelligence", " ai ", "technology", "surveillance",
        "platform", "social media", "data", "privacy", "algorithm",
        "cybersecurity", "digital", "internet", "semiconductor",
    ),
}
INDIA_TERMS = (
    "india", "indian", "new delhi", "modi", "lok sabha", "rajya sabha",
    "supreme court of india", "reserve bank of india", "election commission of india",
    "bharat", "south asia",
)


@dataclass
class ScoredTopic:
    title: str
    description: str
    source: str
    url: str
    published_at: str | None
    total_score: int
    channel_fit: int
    recency: int
    india_relevance: int
    topic_areas: list[str]
    rationale: list[str]
    status: str = "lead_only_not_fact_checked"

    def to_dict(self) -> dict:
        return asdict(self)


def _clamp(value: int, low: int = 0, high: int = 5) -> int:
    return max(low, min(high, value))


def score_topic(topic: TrendingTopic, now: datetime | None = None) -> ScoredTopic | None:
    """Score a trend lead for channel fit; return None for off-scope items."""
    text = f" {topic.title} {topic.description} ".lower()
    areas = [
        area for area, terms in CHANNEL_TERMS.items()
        if any(term in text for term in terms)
    ]
    if not areas:
        return None

    channel_fit = _clamp(2 + len(areas))
    published = topic.timestamp
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (current - published).total_seconds() / 86400)
    recency = 5 if age_days <= 1 else 4 if age_days <= 2 else 3 if age_days <= 4 else 2 if age_days <= 7 else 1

    india_hits = sum(1 for term in INDIA_TERMS if term in text)
    india_relevance = _clamp(india_hits + (1 if "south asia" in text else 0))
    source_signal = 3 if topic.source in {"google_news", "reddit"} and topic.url.startswith("http") else 1
    total = channel_fit * 3 + recency * 2 + india_relevance + source_signal
    rationale = [f"Matches {', '.join(areas)}"]
    if india_relevance:
        rationale.append("Has an India/South Asia connection")
    rationale.append("Trend signal only; evidence quality and originality still require research")
    return ScoredTopic(
        title=topic.title,
        description=topic.description,
        source=topic.source,
        url=topic.url,
        published_at=published.isoformat(),
        total_score=total,
        channel_fit=channel_fit,
        recency=recency,
        india_relevance=india_relevance,
        topic_areas=areas,
        rationale=rationale,
    )


def scout_topics(
    *,
    limit: int = 20,
    now: datetime | None = None,
    topics: Iterable[TrendingTopic] | None = None,
    topic_ledger: TopicLedger | None = None,
) -> list[ScoredTopic]:
    """Collect, rank and deduplicate topic leads without approving them."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    collected = list(topics) if topics is not None else get_trending_topics(
        max_topics=max(30, limit * 4), min_engagement=0, trend_source="all"
    )
    scored: list[ScoredTopic] = []
    seen: set[str] = set()
    for item in collected:
        candidate = score_topic(item, now=now)
        if candidate is None:
            continue
        normalized = re.sub(r"[^a-z0-9 ]", "", candidate.title.lower()).strip()
        normalized = re.sub(r"\\s+", " ", normalized)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if topic_ledger and topic_ledger.is_duplicate("politics-of-everything", candidate.title):
            continue
        scored.append(candidate)
    scored.sort(key=lambda item: (item.total_score, item.recency, item.channel_fit), reverse=True)
    return scored[:limit]


def write_scout_report(topics: list[ScoredTopic], output_path: Path) -> Path:
    """Persist a dated, auditable scouting report."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "channel": "Politics of Everything",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(topics),
        "editorial_status": "unapproved_leads",
        "topics": [topic.to_dict() for topic in topics],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    return output_path
