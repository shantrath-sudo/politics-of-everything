"""Politics of Everything channel operations.

Local-first topic scouting and approval-state controls. This module never
uploads, publishes, or changes YouTube resources.
"""
from __future__ import annotations

import json
import re
import shutil
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

from ai_video_factory.scheduler import TopicLedger

Transport = Callable[[str], str]
USER_AGENT = "PoliticsOfEverything/1.0 (documentary topic scouting)"
DEFAULT_QUERIES = [
    "democracy institutions political power",
    "political economy inequality public finance",
    "geopolitics international relations global institutions",
    "India governance constitution economy policy",
    "technology platforms surveillance artificial intelligence society",
]
STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "by",
    "with", "from", "how", "why", "what", "who", "is", "are", "was",
    "were", "after", "before", "over", "new", "says", "say",
}
FIT_TERMS = {
    "democracy", "government", "politics", "political", "power", "state",
    "constitution", "election", "parliament", "court", "policy", "law",
    "institution", "governance", "economy", "economic", "trade", "debt",
    "inequality", "labour", "labor", "market", "capital", "geopolitics",
    "war", "diplomacy", "china", "india", "united", "nations", "technology",
    "platform", "surveillance", "artificial", "intelligence", "society",
    "culture", "rights", "protest", "movement", "climate", "energy",
}
INDIA_TERMS = {"india", "indian", "delhi", "modi", "parliament", "lok", "sabha", "rajya", "rupee"}
GLOBAL_TERMS = {"global", "world", "international", "un", "china", "america", "us", "europe", "eu", "africa", "asia", "geopolitics"}


class ChannelWorkflowError(RuntimeError):
    """Raised when an editorial workflow transition is invalid."""


DEFAULT_PUBLISHER_FEEDS = (
    ("BBC India", "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml"),
    ("The Hindu", "https://www.thehindu.com/feeder/default.rss"),
    ("Indian Express", "https://indianexpress.com/feed/"),
    ("Business Standard", "https://www.business-standard.com/rss/home_page_top_stories.rss"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
)

GDELT_DOC_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


@dataclass
class TopicCandidate:
    candidate_id: str
    title: str
    summary: str
    url: str
    publishers: list[str] = field(default_factory=list)
    published_at: str | None = None
    queries: list[str] = field(default_factory=list)
    article_urls: list[str] = field(default_factory=list)
    topic_fit: float = 0.0
    india_relevance: float = 0.0
    international_relevance: float = 0.0
    recency: float = 0.0
    source_diversity: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)



def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS and len(token) > 1
    }


def _overlap(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def _recency_score(published_at: str | None, now: datetime) -> float:
    if not published_at:
        return 1.0
    try:
        published = parsedate_to_datetime(published_at)
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        age_hours = max(0.0, (now - published.astimezone(UTC)).total_seconds() / 3600)
    except (TypeError, ValueError, OverflowError):
        return 1.0
    if age_hours <= 24:
        return 5.0
    if age_hours <= 72:
        return 4.0
    if age_hours <= 168:
        return 3.0
    if age_hours <= 336:
        return 2.0
    return 1.0


def _score_candidate(candidate: TopicCandidate, now: datetime) -> None:
    text = f"{candidate.title} {candidate.summary}".lower()
    tokens = _tokens(text)
    fit_hits = len(tokens & FIT_TERMS)
    india_hits = len(tokens & INDIA_TERMS)
    global_hits = len(tokens & GLOBAL_TERMS)
    candidate.topic_fit = min(5.0, 1.0 + fit_hits * 0.65)
    candidate.india_relevance = min(5.0, india_hits * 1.5)
    candidate.international_relevance = min(5.0, global_hits * 1.25)
    candidate.recency = _recency_score(candidate.published_at, now)
    candidate.source_diversity = min(5.0, float(len(set(candidate.publishers))) * 1.5)
    # A transparent discovery priority score, not a factual-confidence score.
    candidate.score = round(
        candidate.topic_fit * 0.30
        + candidate.international_relevance * 0.20
        + candidate.india_relevance * 0.15
        + candidate.recency * 0.20
        + candidate.source_diversity * 0.15,
        3,
    )


def _valid_publisher_url(url: str) -> bool:
    from ai_video_factory.research_pipeline import _is_blocked_host

    try:
        parsed = urlsplit(url)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not _is_blocked_host(parsed.hostname)
        )
    except ValueError:
        return False


def _parse_publisher_rss(
    xml_text: str, publisher: str, query: str
) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    rows: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if title and link and _valid_publisher_url(link):
            rows.append({
                "title": title,
                "url": link,
                "summary": re.sub(r"<[^>]+>", " ", description).strip(),
                "published_at": pub_date,
                "publisher": publisher,
                "query": query,
            })
    return rows


def _read_gdelt(
    queries: list[str], transport: Transport
) -> list[dict[str, str]]:
    # One combined request respects GDELT DOC's request cadence while retaining
    # the channel's broad topic coverage. Search results are discovery leads.
    terms = sorted({term for query in queries for term in re.findall(r"[A-Za-z0-9]+", query)})
    query = "(" + " OR ".join(f'"{term}"' for term in terms) + ")"
    params = urllib.parse.urlencode({
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": "250",
        "timespan": "24h",
        "sort": "DateDesc",
    })
    payload = json.loads(transport(f"{GDELT_DOC_ENDPOINT}?{params}"))
    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    rows: list[dict[str, str]] = []
    for article in articles:
        title = str(article.get("title") or "").strip()
        url = str(article.get("url") or "").strip()
        if not title or not _valid_publisher_url(url):
            continue
        seen = str(article.get("seendate") or "")
        published = ""
        if re.fullmatch(r"\d{14}", seen):
            try:
                published = datetime.strptime(seen, "%Y%m%d%H%M%S").replace(tzinfo=UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
            except ValueError:
                pass
        domain = str(article.get("domain") or urlsplit(url).hostname or "Unknown publisher")
        rows.append({
            "title": title,
            "url": url,
            "summary": "",
            "published_at": published,
            "publisher": domain,
            "query": "GDELT: " + "; ".join(queries),
        })
    return rows


def scout_topics(
    *,
    queries: list[str] | None = None,
    transport: Transport | None = None,
    now: datetime | None = None,
    limit: int = 20,
    ledger_path: Path | None = None,
    resolver: Callable[[str], str] | None = None,
    diagnostics: dict[str, Any] | None = None,
    max_resolution_attempts: int = 80,
) -> list[TopicCandidate]:
    """Discover topics from GDELT DOC (24h) and direct publisher RSS.

    All returned links are original HTTPS publisher URLs. Headlines are leads,
    not verified facts. No paid API or redirect-resolution service is used.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    queries = queries or DEFAULT_QUERIES
    transport = transport or _transport
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    rows: list[dict[str, str]] = []
    failures: list[str] = []
    try:
        rows.extend(_read_gdelt(queries, transport))
    except Exception as error:
        failures.append(f"GDELT DOC: {type(error).__name__}: {str(error)[:240]}")

    # Publisher RSS is deliberately independent of GDELT, so one provider
    # outage does not make the entire scout unavailable.
    with ThreadPoolExecutor(max_workers=min(6, len(DEFAULT_PUBLISHER_FEEDS))) as pool:
        futures = {
            pool.submit(transport, url): (publisher, url)
            for publisher, url in DEFAULT_PUBLISHER_FEEDS
        }
        for future in as_completed(futures):
            publisher, url = futures[future]
            try:
                rows.extend(_parse_publisher_rss(future.result(), publisher, publisher))
            except Exception as error:
                failures.append(f"{publisher} RSS: {type(error).__name__}: {str(error)[:240]}")

    if diagnostics is not None:
        diagnostics.update({
            "providers": ["GDELT DOC", "direct publisher RSS"],
            "queries_requested": 1 + len(DEFAULT_PUBLISHER_FEEDS),
            "feed_failures": len(failures),
            "feed_failure_samples": failures[:8],
            "rss_headlines": len(rows),
            "gdelt_window": "24h",
            "article_url_resolution_attempts": 0,
        })
    if not rows and failures:
        raise ChannelWorkflowError("all topic discovery providers failed: " + "; ".join(failures))

    clusters: list[TopicCandidate] = []
    for row in rows:
        match = next((c for c in clusters if _overlap(c.title, row["title"]) >= 0.55), None)
        if match:
            if row["publisher"] not in match.publishers:
                match.publishers.append(row["publisher"])
            if row["url"] not in match.article_urls:
                match.article_urls.append(row["url"])
            if row["query"] not in match.queries:
                match.queries.append(row["query"])
            if not match.summary and row["summary"]:
                match.summary = row["summary"]
            continue
        candidate_id = __import__("hashlib").sha256(row["title"].lower().encode()).hexdigest()[:12]
        clusters.append(TopicCandidate(
            candidate_id=candidate_id,
            title=row["title"],
            summary=row["summary"],
            url=row["url"],
            publishers=[row["publisher"]],
            published_at=row["published_at"] or None,
            queries=[row["query"]],
            article_urls=[row["url"]],
        ))

    clusters_before_ledger = len(clusters)
    for candidate in clusters:
        _score_candidate(candidate, now)
    if ledger_path:
        ledger = TopicLedger(ledger_path)
        clusters = [c for c in clusters if not ledger.is_duplicate("politics-of-everything", c.title)]
    clusters_after_ledger = len(clusters)
    clusters.sort(key=lambda c: (c.score, c.source_diversity, c.recency), reverse=True)
    selected = clusters[:limit]
    if diagnostics is not None:
        diagnostics.update({
            "clusters_before_ledger": clusters_before_ledger,
            "duplicates_filtered": clusters_before_ledger - clusters_after_ledger,
            "clusters_after_ledger": clusters_after_ledger,
            "resolver_attempts": 0,
            "resolver_failures": 0,
            "resolver_failure_samples": [],
            "resolved_candidates": len(selected),
            "resolution_attempt_limit": 0,
            "resolution_attempt_limit_reached": False,
            "resolution_stopped_for_rate_limit": False,
        })
    return selected


def save_scout_report(
    candidates: list[TopicCandidate],
    output_dir: Path,
    *,
    on_date: date | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> Path:
    output_dir = Path(output_dir)
    report_date = on_date or datetime.now().date()
    destination = output_dir / "scouting" / f"{report_date.isoformat()}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "channel": "politics-of-everything",
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": "Discovery signals only. Headlines are leads, not verified facts or editorial approval.",
        "candidate_count": len(candidates),
        "diagnostics": diagnostics or {},
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Human-readable companion report; JSON remains the machine-readable source.
    lines = [
        f"# Politics of Everything — Topic Shortlist ({report_date.isoformat()})",
        "",
        "> Discovery signals only. Headlines are leads, not verified facts or editorial approval.",
        "",
    ]
    if diagnostics:
        lines.extend([
            "## Discovery diagnostics",
            "",
            f"- RSS headlines received: {diagnostics.get('rss_headlines', 0)}",
            f"- Feed requests failed: {diagnostics.get('feed_failures', 0)} of {diagnostics.get('queries_requested', 0)}",
            f"- Unique headline clusters: {diagnostics.get('clusters_before_ledger', 0)}",
            f"- Previously covered topics filtered: {diagnostics.get('duplicates_filtered', 0)}",
            f"- Article URL resolution attempts: {diagnostics.get('resolver_attempts', 0)}",
            f"- Article URL resolution failures: {diagnostics.get('resolver_failures', 0)}",
            f"- Candidates with resolved publisher URLs: {diagnostics.get('resolved_candidates', 0)}",
            "",
        ])
        for failure in diagnostics.get("feed_failure_samples", []):
            lines.append(f"- Feed error: {failure}")
        for failure in diagnostics.get("resolver_failure_samples", []):
            lines.append(f"- URL resolution error: {failure}")
        lines.append("")
    if not candidates:
        lines.extend(["No candidates passed the current topic and source filters. See discovery diagnostics above for the stage that produced zero candidates.", ""])
    for index, candidate in enumerate(candidates, 1):
        lines.extend([
            f"## {index}. {candidate.title}",
            "",
            f"- Candidate ID: `{candidate.candidate_id}`",
            f"- Approve command: `politics-channel approve-topic {candidate.candidate_id} --date {report_date.isoformat()}`",
            f"- Priority score: **{candidate.score:.2f}/5**",
            f"- Topic fit: {candidate.topic_fit:.1f}/5",
            f"- India relevance: {candidate.india_relevance:.1f}/5",
            f"- International relevance: {candidate.international_relevance:.1f}/5",
            f"- Recency: {candidate.recency:.1f}/5",
            f"- Publishers: {', '.join(candidate.publishers) or 'Not identified'}",
            f"- Matched queries: {', '.join(candidate.queries) or 'Not recorded'}",
            "",
            candidate.summary or "No publisher summary was supplied.",
            "",
            "Sources:",
        ])
        lines.extend(f"- {url}" for url in (candidate.article_urls or [candidate.url]) if url)
        lines.append("")
    lines.extend([
        "---",
        "A candidate requires explicit Editor-in-Chief approval before research begins.",
        f"Use its Candidate ID with `politics-channel approve-topic CANDIDATE_ID --date {report_date.isoformat()}`.",
        "",
    ])
    markdown_path = destination.with_suffix(".md")
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return destination


VALID_STAGES = (
    "topic_pending",
    "topic_approved",
    "research_ready",
    "script_pending",
    "script_approved",
    "production_ready",
    "final_pending",
    "final_approved",
)
ALLOWED_TRANSITIONS = {
    "topic_pending": {"topic_approved"},
    "topic_approved": {"research_ready"},
    "research_ready": {"script_pending"},
    "script_pending": {"script_approved"},
    "script_approved": {"production_ready"},
    "production_ready": {"final_pending"},
    "final_pending": {"final_approved"},
    "final_approved": set(),
}


class WorkflowStore:
    """Persistent project states with explicit, fail-closed human approval gates."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", project_id):
            raise ChannelWorkflowError("invalid project id")
        return self.root / f"{project_id}.json"

    def create(self, project_id: str, candidate: TopicCandidate) -> dict[str, Any]:
        path = self._path(project_id)
        if path.exists():
            raise ChannelWorkflowError(f"project already exists: {project_id}")
        record = {
            "project_id": project_id,
            "channel": "politics-of-everything",
            "topic": candidate.to_dict(),
            "stage": "topic_pending",
            "approvals": {"topic": False, "script": False, "final": False},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "artifacts": {},
            "revision_count": 0,
            "pending_revision_feedback": None,
            "revision_requests": [],
            "history": [{"stage": "topic_pending", "event": "project_created"}],
        }
        path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    def get(self, project_id: str) -> dict[str, Any]:
        path = self._path(project_id)
        if not path.is_file():
            raise ChannelWorkflowError(f"project not found: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def transition(self, project_id: str, next_stage: str, *, artifact: str | None = None) -> dict[str, Any]:
        record = self.get(project_id)
        current = record["stage"]
        if next_stage not in ALLOWED_TRANSITIONS.get(current, set()):
            raise ChannelWorkflowError(f"invalid workflow transition: {current} -> {next_stage}")
        if next_stage == "script_pending" and not record["artifacts"].get("research_dossier") and not artifact:
            raise ChannelWorkflowError("script submission requires a completed research dossier")
        if next_stage == "script_approved" and not record["artifacts"].get("script"):
            raise ChannelWorkflowError("script approval requires a saved script artifact")
        if next_stage == "production_ready" and not artifact:
            raise ChannelWorkflowError("production readiness requires a render and QA manifest")
        if next_stage == "final_pending" and not record["artifacts"].get("production_manifest") and not artifact:
            raise ChannelWorkflowError("final submission requires a completed production manifest")
        if next_stage == "final_approved" and not record["artifacts"].get("final_video"):
            raise ChannelWorkflowError("final approval requires a final video artifact")
        if artifact:
            if next_stage == "research_ready":
                record["artifacts"]["research_dossier"] = artifact
            elif next_stage == "script_pending":
                record["artifacts"]["script"] = artifact
            elif next_stage == "production_ready":
                record["artifacts"]["production_manifest"] = artifact
            elif next_stage == "final_pending":
                record["artifacts"]["final_video"] = artifact
        record["stage"] = next_stage
        record["updated_at"] = datetime.now(UTC).isoformat()
        record["history"].append({"stage": next_stage, "event": "explicit_transition"})
        if next_stage == "topic_approved":
            record["approvals"]["topic"] = True
        elif next_stage == "script_approved":
            record["approvals"]["script"] = True
        elif next_stage == "final_approved":
            record["approvals"]["final"] = True
        self._path(project_id).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record

    def request_revision(self, project_id: str, feedback: str) -> dict[str, Any]:
        """Reopen research/script production after a rejected script or final video."""
        record = self.get(project_id)
        current = record["stage"]
        if current not in {"script_pending", "final_pending"}:
            raise ChannelWorkflowError(
                f"revision can only be requested from script_pending or final_pending, got {current}"
            )
        note = (feedback or "").strip()
        if not note:
            raise ChannelWorkflowError("revision feedback cannot be empty")
        if len(note) > 2000:
            raise ChannelWorkflowError("revision feedback must be 2000 characters or fewer")

        record["revision_count"] = int(record.get("revision_count", 0)) + 1
        record["pending_revision_feedback"] = note
        previous_artifacts = {
            key: record["artifacts"][key]
            for key in ("script", "script_markdown", "production_manifest", "final_video", "delivery_package", "delivery_manifest")
            if record["artifacts"].get(key)
        }
        archived_package = None
        old_package_value = previous_artifacts.get("delivery_package")
        if old_package_value:
            old_package = Path(old_package_value)
            if old_package.is_dir():
                archive_root = old_package.parent / "revisions" / project_id
                archive_root.mkdir(parents=True, exist_ok=True)
                archived_package = archive_root / f"revision-{record['revision_count']}"
                if archived_package.exists():
                    shutil.rmtree(archived_package)
                shutil.move(str(old_package), str(archived_package))
                previous_artifacts["delivery_package"] = str(archived_package)
                old_manifest = previous_artifacts.get("delivery_manifest")
                if old_manifest:
                    previous_artifacts["delivery_manifest"] = str(
                        archived_package / Path(old_manifest).name
                    )
        record.setdefault("revision_requests", []).append({
            "revision": record["revision_count"],
            "from_stage": current,
            "feedback": note,
            "previous_artifacts": previous_artifacts,
            "requested_at": datetime.now(UTC).isoformat(),
        })
        record["stage"] = "research_ready"
        record["approvals"]["script"] = False
        record["approvals"]["final"] = False
        record["artifacts"].pop("production_manifest", None)
        record["artifacts"].pop("final_video", None)
        record["artifacts"].pop("delivery_package", None)
        record["artifacts"].pop("delivery_manifest", None)
        record.pop("delivered_at", None)
        record["updated_at"] = datetime.now(UTC).isoformat()
        record["history"].append({
            "stage": "research_ready",
            "event": "revision_requested",
            "from_stage": current,
            "revision": record["revision_count"],
            "archived_delivery_package": str(archived_package) if archived_package else None,
        })
        self._path(project_id).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        return record

    def attach_artifact(
        self, project_id: str, key: str, artifact_path: str | Path
    ) -> dict[str, Any]:
        """Attach a companion artifact such as the readable Markdown script."""
        path = Path(artifact_path)
        if not key.strip() or not path.is_file():
            raise ChannelWorkflowError("artifact key and existing file are required")
        record = self.get(project_id)
        record["artifacts"][key] = str(path)
        record["updated_at"] = datetime.now(UTC).isoformat()
        record["history"].append({
            "stage": record["stage"],
            "event": "artifact_attached",
            "artifact": key,
            "path": str(path),
        })
        self._path(project_id).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        return record

    def record_delivery(
        self, project_id: str, package_dir: str | Path, manifest_path: str | Path
    ) -> dict[str, Any]:
        """Record the private review package so final approval cannot happen early."""
        record = self.get(project_id)
        if record["stage"] != "final_pending":
            raise ChannelWorkflowError(
                f"delivery requires final_pending, got {record['stage']}"
            )
        package = Path(package_dir)
        manifest = Path(manifest_path)
        if not package.is_dir() or not manifest.is_file():
            raise ChannelWorkflowError("review package directory or delivery manifest is missing")
        if record["artifacts"].get("delivery_manifest") == str(manifest):
            return record
        record["artifacts"]["delivery_package"] = str(package)
        record["artifacts"]["delivery_manifest"] = str(manifest)
        delivered_at = datetime.now(UTC).isoformat()
        record["delivered_at"] = delivered_at
        record["updated_at"] = delivered_at
        record["history"].append({
            "stage": "final_pending",
            "event": "review_package_delivered",
            "delivery_manifest": str(manifest),
        })
        self._path(project_id).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        return record

    def list(self) -> list[dict[str, Any]]:
        records = []
        for path in sorted(self.root.glob("*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return records
