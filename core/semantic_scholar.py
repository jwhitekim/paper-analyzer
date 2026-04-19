import os
import re
import time
import requests
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

_ARXIV_RE = re.compile(r"arxiv\.org/abs/([\d.]+v?\d*)")
_DOI_RE   = re.compile(r"10\.\d{4,}/[^\s&?#\"']+")
_PMID_RE  = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")

MAX_AUTHORS = 3

BASE_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS_PAPER = "title,year,venue,externalIds,abstract,authors,citationCount"
FIELDS_AUTHOR = "name,hIndex,citationCount,papers.title,papers.citationCount,papers.year"

# API 키 없을 때 요청 간 최소 간격 (초)
_ANON_DELAY = 1.0


def _has_api_key() -> bool:
    return bool(os.getenv("S2_API_KEY", ""))


def _session() -> requests.Session:
    s = requests.Session()
    if _has_api_key():
        s.headers.update({"x-api-key": os.environ["S2_API_KEY"]})
    return s


def _get(path: str, params: dict) -> requests.Response:
    """모든 S2 API 요청의 단일 진입점. 429 시 재시도, 무인증 시 딜레이."""
    if not _has_api_key():
        time.sleep(_ANON_DELAY)

    s = _session()
    for attempt in range(4):
        resp = s.get(f"{BASE_URL}/{path}", params=params, timeout=15)
        if resp.status_code != 429:
            break
        wait = 2 ** attempt
        time.sleep(wait)

    if resp.status_code == 403:
        raise PermissionError("Semantic Scholar API 접근 거부 (403) — .env에 S2_API_KEY를 설정하세요.")
    if resp.status_code == 429:
        raise ConnectionError("Semantic Scholar API rate limit — 잠시 후 다시 시도하거나 S2_API_KEY를 설정하세요.")
    resp.raise_for_status()
    return resp


def parse_url(url: str) -> tuple[str, str]:
    """
    학술 사이트 URL에서 식별자를 추출한다.
    반환: (lookup_type, identifier)
      lookup_type: "arxiv" | "doi" | "s2" | "pmid" | "unknown"

    지원 사이트: arxiv, doi.org, dl.acm.org, ieeexplore, nature, springer,
                 sciencedirect, pubmed, semanticscholar, researchgate,
                 wiley, tandfonline, mdpi, frontiersin
    """
    # 1. arXiv ID
    m = _ARXIV_RE.search(url)
    if m:
        return "arxiv", m.group(1)

    # 2. Semantic Scholar 고유 ID (DOI 검색 전에 확인)
    if "semanticscholar.org/paper/" in url:
        s2_id = url.split("/paper/")[-1].split("/")[0].split("?")[0].strip()
        if s2_id:
            return "s2", s2_id

    # 3. PubMed ID (DOI 없는 경우 대비)
    m = _PMID_RE.search(url)
    if m:
        return "pmid", m.group(1)

    # 4. DOI 패턴 — URL 어디서든 추출 (대부분의 사이트 커버)
    #    doi.org, dl.acm.org/doi/, ieeexplore, nature, springer,
    #    sciencedirect, wiley, tandfonline, mdpi, frontiersin 등
    m = _DOI_RE.search(url)
    if m:
        return "doi", m.group(0).rstrip(".")

    # 5. ResearchGate는 DOI가 URL에 없을 수 있음 → unknown으로 처리
    return "unknown", url


def is_arxiv_url(text: str) -> bool:
    return bool(_ARXIV_RE.search(text))


def fetch_paper_by_url(url: str) -> Optional[dict]:
    lookup_type, identifier = parse_url(url)
    if lookup_type == "arxiv":
        s2_paper_id = f"ArXiv:{identifier}"
    elif lookup_type == "doi":
        s2_paper_id = f"DOI:{identifier}"
    elif lookup_type == "pmid":
        s2_paper_id = f"PMID:{identifier}"
    elif lookup_type == "s2":
        s2_paper_id = identifier
    else:
        return None

    resp = _get(f"paper/{s2_paper_id}", {"fields": FIELDS_PAPER})
    data = resp.json()
    return data if data.get("paperId") else None


def fetch_paper_by_id(paper_id: str) -> Optional[dict]:
    resp = _get(f"paper/{paper_id}", {"fields": FIELDS_PAPER})
    data = resp.json()
    return data if data.get("paperId") else None


def search_papers_by_title(title: str, limit: int = 5) -> list[dict]:
    resp = _get("paper/search", {"query": title, "limit": limit, "fields": FIELDS_PAPER})
    return resp.json().get("data", [])


def _fetch_author_detail(author_id: str) -> Optional[dict]:
    resp = _get(f"author/{author_id}", {"fields": FIELDS_AUTHOR})
    return resp.json()


def _enrich_one(author: dict) -> dict:
    author_id = author.get("authorId")
    if not author_id:
        return author
    try:
        detail = _fetch_author_detail(author_id)
        papers = detail.get("papers", [])
        top_papers = sorted(papers, key=lambda p: p.get("citationCount") or 0, reverse=True)[:5]
        return {
            "name": detail.get("name", author.get("name", "")),
            "authorId": author_id,
            "hIndex": detail.get("hIndex"),
            "citationCount": detail.get("citationCount"),
            "topPapers": top_papers,
        }
    except Exception:
        return author


def enrich_authors(paper: dict) -> list[dict]:
    authors = paper.get("authors", [])[:MAX_AUTHORS]
    if not authors:
        return []

    if _has_api_key():
        # API 키 있으면 병렬
        results = [None] * len(authors)
        with ThreadPoolExecutor(max_workers=MAX_AUTHORS) as pool:
            futures = {pool.submit(_enrich_one, a): i for i, a in enumerate(authors)}
            for fut in as_completed(futures):
                results[futures[fut]] = fut.result()
        return results
    else:
        # API 키 없으면 순차 (_get 내부 딜레이 적용됨)
        return [_enrich_one(a) for a in authors]
