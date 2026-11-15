"""Politics of Everything channel operations.

Local-first topic scouting and approval-state controls. This module never
uploads, publishes, or changes YouTube resources.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
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


def _transport(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        if getattr(response, "status", 200) != 200:
            raise ChannelWorkflowError(f"RSS request returned HTTP {response.status}")
        return response.read().decode("utf-8", errors="replace")


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


def _resolve_article_url(url: str) -> str:
    """Resolve a Google News redirect to its HTTPS publisher URL safely."""
    from ai_video_factory.research_pipeline import _is_blocked_host

    def validate(candidate: str) -> None:
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ChannelWorkflowError("article link must resolve to a credential-free HTTPS URL")
        if _is_blocked_host(parsed.hostname):
            raise ChannelWorkflowError("article link resolved to a blocked or private host")

    class SafeRedirects(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            destination = urljoin(req.full_url, newurl)
            validate(destination)
            return super().redirect_request(req, fp, code, msg, headers, destination)

    validate(url)
    opener = build_opener(SafeRedirects())
    request = Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=12) as response:
            resolved = response.geturl()
    except HTTPError as error:
        if error.code not in {405, 501}:
            raise ChannelWorkflowError(f"could not resolve article link (HTTP {error.code})") from error
        request = Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
        with opener.open(request, timeout=12) as response:
            resolved = response.geturl()
    validate(resolved)
    host = (urlsplit(resolved).hostname or "").lower()
    if host == "news.google.com" or host.endswith(".news.google.com"):
        raise ChannelWorkflowError("Google News did not resolve to the publisher article")
    return resolved


FEED_EDITIONS = (
    ("en-IN", "IN", "IN:en"),
    ("en-US", "US", "US:en"),
)


def _read_feed(
    query: str,
    transport: Transport,
    edition: tuple[str, str, str] = ("en-IN", "IN", "IN:en"),
) -> list[dict[str, str]]:
    hl, gl, ceid = edition
    params = urllib.parse.urlencode({"q": query, "hl": hl, "gl": gl, "ceid": ceid})
    url = f"https://news.google.com/rss/search?{params}"
    try:
        root = ET.fromstring(transport(url))
    except Exception as error:
        raise ChannelWorkflowError(
            f"could not parse RSS results for {query!r} ({gl} edition): {error}"
        ) from error
    rows = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip() or None
        source_node = item.find("source")
        publisher = (source_node.text or "").strip() if source_node is not None else ""
        if title and link:
            rows.append({
                "title": title,
                "url": link,
                "summary": re.sub(r"<[^>]+>", " ", description).strip(),
                "published_at": pub_date or "",
                "publisher": publisher or "Unknown publisher",
                "query": query,
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
) -> list[TopicCandidate]:
    """Discover and rank political/economic/societal topics from public RSS.

    RSS headlines are leads, not verified facts. No LLM or paid API is called.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    queries = queries or DEFAULT_QUERIES
    transport = transport or _transport
    resolver = resolver or _resolve_article_url
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    rows: list[dict[str, str]] = []
    failures: list[str] = []
    # Run India and international editions concurrently so daily scouting stays bounded.
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(queries) * len(FEED_EDITIONS)))) as pool:
        futures = {
            pool.submit(_read_feed, query, transport, edition): (query, edition)
            for query in queries
            for edition in FEED_EDITIONS
        }
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception as error:
                failures.append(str(error))
    if not rows and failures:
        raise ChannelWorkflowError("all topic RSS queries failed: " + "; ".join(failures))

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

    for candidate in clusters:
        _score_candidate(candidate, now)

    if ledger_path:
        ledger = TopicLedger(ledger_path)
        clusters = [
            c for c in clusters
            if not ledger.is_duplicate("politics-of-everything", c.title)
        ]
    clusters.sort(key=lambda c: (c.score, c.source_diversity, c.recency), reverse=True)
    resolved: list[TopicCandidate] = []
    for candidate in clusters:
        article_urls = candidate.article_urls[:4]
        direct_by_index: dict[int, str] = {}
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(article_urls)))) as pool:
            futures = {
                pool.submit(resolver, article_url): index
                for index, article_url in enumerate(article_urls)
            }
            for future in as_completed(futures):
                try:
                    direct_by_index[futures[future]] = future.result()
                except Exception:
                    continue
        direct_urls = list(dict.fromkeys(
            direct_by_index[index]
            for index in sorted(direct_by_index)
        ))
        if not direct_urls:
            continue
        candidate.article_urls = direct_urls
        candidate.url = direct_urls[0]
        resolved.append(candidate)
        if len(resolved) >= limit:
            break
    return resolved


def save_scout_report(candidates: list[TopicCandidate], output_dir: Path, *, on_date: date | None = None) -> Path:
    output_dir = Path(output_dir)
    report_date = on_date or datetime.now().date()
    destination = output_dir / "scouting" / f"{report_date.isoformat()}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "channel": "politics-of-everything",
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": "Discovery signals only. Headlines are leads, not verified facts or editorial approval.",
        "candidate_count": len(candidates),
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
    if not candidates:
        lines.extend(["No candidates passed the current topic and source filters.", ""])
    for index, candidate in enumerate(candidates, 1):
        lines.extend([
            f"## {index}. {candidate.title}",
            "",
            f"- Candidate ID: `{candidate.candidate_id}`",
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
        "Use its Candidate ID with `politics-channel approve-topic CANDIDATE_ID`.",
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
        record.setdefault("revision_requests", []).append({
            "revision": record["revision_count"],
            "from_stage": current,
            "feedback": note,
            "requested_at": datetime.now(UTC).isoformat(),
        })
        record["stage"] = "research_ready"
        record["approvals"]["script"] = False
        record["approvals"]["final"] = False
        record["artifacts"].pop("production_manifest", None)
        record["artifacts"].pop("final_video", None)
        record["updated_at"] = datetime.now(UTC).isoformat()
        record["history"].append({
            "stage": "research_ready",
            "event": "revision_requested",
            "from_stage": current,
            "revision": record["revision_count"],
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
