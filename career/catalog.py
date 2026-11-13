"""공개 출처·직무·영상 목록을 읽으며 개인 기록이나 네트워크를 사용하지 않음."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
import json
from pathlib import Path
import re
from urllib.parse import urlparse

GOAL_IDS = ("arm", "nav", "vision", "field", "physical", "platform")
COURSE_LABELS = {"taught": "11기 수업", "partial": "11기 일부", "extra": "추가 학습", "unverified": "확인 대기"}
RELATION_LABELS = {"primary": "연결된 로드맵", "adjacent_specialization": "함께 참고할 로드맵",
                   "shared_skills_only": "일부 공통 기술만 연결"}
DATA = Path(__file__).with_name("data")


class CatalogError(ValueError):
    """파일은 있으나 공개 자료의 형식이나 연결을 확인하지 못했음."""


def _text(value, nullable=False):
    if nullable and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CatalogError("자료의 글 항목을 확인하지 못했습니다.")
    return value


def _date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(_text(value)).isoformat()
    except ValueError:
        raise CatalogError("자료의 날짜 형식을 확인하지 못했습니다.") from None


def _url(value):
    value = _text(value)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise CatalogError("공개 출처 주소를 확인하지 못했습니다.")
    return value


def _items(value):
    if not isinstance(value, list):
        raise CatalogError("자료 목록의 형식을 확인하지 못했습니다.")
    return tuple(_text(item) for item in value)


def _unique(rows, key="id"):
    ids = [row[key] for row in rows]
    if len(ids) != len(set(ids)):
        raise CatalogError("자료 식별자가 겹칩니다.")


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    author: str
    url: str
    upload_date: str | None
    uploaded_at_utc: str | None
    duration_seconds: int | None
    origin: str
    topic: str
    summary: str
    learning_use: str
    limitations: str
    verification_scope: str
    checked_date: str
    embeddable: bool | None
    source_urls: tuple[str, ...] = ()
    transcript_review: str = "not_reviewed"
    visual_review: str = "not_reviewed"

    @property
    def duration_label(self):
        if self.duration_seconds is None:
            return "길이 미확인"
        minutes, seconds = divmod(self.duration_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"

    @property
    def date_label(self):
        return self.upload_date or "업로드 날짜 미확인"

    @property
    def review_label(self):
        return {"metadata_only": "제목·설명 확인", "creator_text_sections_checked": "제작자 본문 일부 확인",
                "full_transcript_reviewed": "전체 대본 검토 완료"}.get(
            self.verification_scope, "내용 확인 범위 미확인")


@dataclass(frozen=True)
class Paper:
    paper_id: str
    title: str
    url: str
    published_date: str | None
    summary: str
    beginner_explanation: str
    checked_date: str
    verification_scope: str = "검토 범위 미확인"
    license_label: str = "이용 조건 미확인"
    license_url: str = ""
    license_scope: str = ""
    prerequisites: tuple[str, ...] = ()
    figure_description: tuple[str, ...] = ()
    examined_version: str = ""
    method_url: str = ""
    adoption_urls: tuple[str, ...] = ()


@dataclass
class Catalog:
    industries: tuple = ()
    products: tuple = ()
    roles: tuple = ()
    sources: tuple = ()
    goals: tuple = ()
    videos: tuple[Video, ...] = ()
    papers: tuple[Paper, ...] = ()
    states: dict = field(default_factory=lambda: {"roles": "unavailable", "videos": "unavailable", "papers": "unavailable"})
    errors: dict = field(default_factory=dict)
    version: str = ""
    roadmap_revision: str = ""
    roadmap_updated: str = ""
    organization_caption: str = "회사마다 조직 이름과 업무 범위가 다릅니다. 공개 자료의 사례를 보여 줍니다."

    def role(self, role_id):
        return next((row for row in self.roles if row["id"] == role_id), None)

    def goal(self, goal_id):
        return next((row for row in self.goals if row["goal_id"] == goal_id), None)

    def roles_for(self, industry_id=None, product_id=None):
        return tuple(row for row in self.roles
                     if (not industry_id or industry_id in row["industry_ids"])
                     and (not product_id or product_id in row["product_ids"]))


def sort_videos(videos):
    """확인한 업로드 날짜 내림차순으로 정렬하고 미확인 날짜를 뒤에 둠."""
    def key(video):
        # 날짜만 아는 항목의 시각은 만들지 않으며 같은 날에는 ID로 순서를 고정함.
        stamp = video.uploaded_at_utc or ""
        return (-(date.fromisoformat(video.upload_date).toordinal()) if video.upload_date else 0,
                -datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() if stamp else float("inf"), video.video_id)
    return tuple(sorted(videos, key=key))


def _videos(raw):
    rows = raw["videos"]
    if not isinstance(rows, list):
        raise CatalogError("영상 목록을 확인하지 못했습니다.")
    result = []
    for row in rows:
        vid = _text(row["video_id"])
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            raise CatalogError("영상 식별자를 확인하지 못했습니다.")
        url = _url(row["url"])
        if url != f"https://www.youtube.com/watch?v={vid}":
            raise CatalogError("영상 식별자와 원본 주소가 일치하지 않습니다.")
        stamp = row.get("uploaded_at_utc")
        if stamp is not None:
            stamp = _text(stamp)
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None or row.get("upload_date") is None:
                raise CatalogError("영상 날짜의 시간대를 확인하지 못했습니다.")
        duration = row.get("duration_seconds")
        if duration is not None and (type(duration) is not int or duration < 0):
            raise CatalogError("영상 길이를 확인하지 못했습니다.")
        embeddable = row.get("embeddable")
        if embeddable is not None and type(embeddable) is not bool:
            raise CatalogError("영상 재생 허용 정보를 확인하지 못했습니다.")
        origin = row["origin"]
        if origin not in ("selected", "additional"):
            raise CatalogError("영상의 목록 구분을 확인하지 못했습니다.")
        result.append(Video(vid, _text(row["title"]), _text(row["author"]), url, _date(row.get("upload_date")), stamp,
                            duration, origin, _text(row["topic"]), _text(row["summary"]), _text(row["learning_use"]),
                            _text(row["limitations"]), _text(row["verification_scope"]), _date(row["checked_date"]),
                            embeddable, tuple(_url(url) for url in row.get("source_urls", [])),
                            _text(row.get("transcript_review", "not_reviewed")), _text(row.get("visual_review", "not_reviewed"))))
    if len({video.video_id for video in result}) != len(result):
        raise CatalogError("같은 영상이 목록에 겹칩니다.")
    return sort_videos(result)


def _roles(raw):
    industries, products, roles, sources, goals = (raw[key] for key in ("industries", "products", "roles", "sources", "goals"))
    for rows in (industries, products, roles, sources):
        if not isinstance(rows, list):
            raise CatalogError("직무 자료 목록을 확인하지 못했습니다.")
        _unique(rows)
    if tuple(goal["goal_id"] for goal in goals) != GOAL_IDS:
        raise CatalogError("기존 목표 목록과 연결을 확인하지 못했습니다.")
    for source in sources:
        _text(source["title"])
        _url(source["url"])
        _date(source["checked_date"])
        _date(source.get("published_date"))
        _text(source["summary"])
    industry_ids = {item["id"] for item in industries}
    product_ids = {item["id"] for item in products}
    source_ids = {item["id"] for item in sources}
    node_ids = {goal["goal_id"]: {node["node_id"] for node in goal["nodes"]} for goal in goals}
    for item in industries:
        _text(item["label"])
    for item in products:
        _text(item["label"])
        if not set(_items(item["industry_ids"])) <= industry_ids or item["status"] != "learning_example":
            raise CatalogError("제품 예시의 산업 연결을 확인하지 못했습니다.")
    for role in roles:
        for key in ("title", "team_label", "team_note"):
            _text(role[key])
        for key in ("inputs", "tasks", "outputs"):
            _items(role[key])
        for key, allowed in (("industry_ids", industry_ids), ("product_ids", product_ids), ("source_ids", source_ids)):
            if not set(_items(role[key])) <= allowed:
                raise CatalogError("직무와 출처의 연결을 확인하지 못했습니다.")
        for link in role["goal_links"]:
            if link["goal_id"] not in GOAL_IDS or link["relation"] not in RELATION_LABELS:
                raise CatalogError("직무와 기존 목표의 연결을 확인하지 못했습니다.")
        for node in role["roadmap_nodes"]:
            if node["node_id"] not in node_ids.get(node["goal_id"], set()) or node["course_status"] not in COURSE_LABELS:
                raise CatalogError("학습 순서와 수업 범위의 연결을 확인하지 못했습니다.")
            _text(node["label"])
    return {"industries": tuple(industries), "products": tuple(products), "roles": tuple(roles), "sources": tuple(sources),
            "goals": tuple(goals), "version": _text(raw["version"]), "roadmap_revision": _text(raw["roadmap_revision"]),
            "roadmap_updated": _date(raw["roadmap_updated"]), "organization_caption": _text(raw["organization_caption"])}


def _papers(raw):
    result = []
    for row in raw["papers"]:
        result.append(Paper(_text(row["paper_id"]), _text(row["title"]), _url(row["url"]), _date(row.get("published_date")),
                            _text(row["summary"]), _text(row["beginner_explanation"]), _date(row["checked_date"]),
                            _text(row.get("verification_scope", "검토 범위 미확인")),
                            _text(row.get("license_label", "이용 조건 미확인")),
                            _url(row["license_url"]) if row.get("license_url") else "", row.get("license_scope", ""),
                            _items(row.get("prerequisites", [])), _items(row.get("figure_description", [])),
                            row.get("examined_version", ""), _url(row["method_url"]) if row.get("method_url") else "",
                            tuple(_url(url) for url in row.get("adoption_urls", []))))
    if len({paper.paper_id for paper in result}) != len(result):
        raise CatalogError("논문 식별자가 겹칩니다.")
    return tuple(result)


def load_catalog(directory=None):
    """자료별로 읽기 실패와 빈 목록을 구분하며 다른 자료는 계속 제공함."""
    directory = Path(directory) if directory is not None else DATA
    catalog = Catalog()
    for kind, filename, parse in (("roles", "roles.json", _roles), ("videos", "videos.json", _videos),
                                  ("papers", "papers.json", _papers)):
        try:
            raw = json.loads((directory / filename).read_text(encoding="utf-8"))
            if type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
                raise CatalogError("자료 버전을 확인하지 못했습니다.")
            parsed = parse(raw)
            if kind == "roles":
                for key, value in parsed.items():
                    setattr(catalog, key, value)
                present = catalog.roles
            else:
                setattr(catalog, kind, parsed)
                present = parsed
            catalog.states[kind] = "ready" if present else "empty"
        except FileNotFoundError:
            catalog.states[kind] = "unavailable"
        except (OSError, UnicodeError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            catalog.states[kind] = "invalid"
            catalog.errors[kind] = "자료를 읽지 못했습니다. 프로그램을 업데이트한 뒤 다시 열어 주세요."
    return catalog
