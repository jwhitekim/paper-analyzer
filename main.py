from calendar import c
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.semantic_scholar import (
    parse_url, fetch_paper_by_url,
    fetch_paper_by_id, search_papers_by_title, enrich_authors,
)
from core.analyzer import analyze_paper, current_provider
from core.journal_quality import lookup_venue

app = FastAPI(title="Paper Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "provider": current_provider()})


@app.post("/search")
async def search(query: str = Form(...)):
    try:
        query = query.strip()

        if query.startswith("http"):
            lookup_type, _ = parse_url(query)
            if lookup_type == "unknown":
                return JSONResponse({"type": "unsupported_url"})
            return JSONResponse({"type": "url", "query": query})

        # 제목 검색 → 후보 5개
        results = search_papers_by_title(query, limit=5)
        candidates = [
            {
                "paperId": p.get("paperId"),
                "title": p.get("title"),
                "year": p.get("year"),
                "venue": p.get("venue"),
                "citationCount": p.get("citationCount"),
            }
            for p in results
        ]
        print(candidates)
        return JSONResponse({"type": "candidates", "data": candidates})
    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.post("/analyze")
async def analyze(paper_id: str = Form(None), url: str = Form(None)):
    try:
        if url:
            paper = fetch_paper_by_url(url)
        elif paper_id:
            paper = fetch_paper_by_id(paper_id)
        else:
            return JSONResponse({"error": "paper_id 또는 url이 필요합니다."})

        if not paper:
            return JSONResponse({"error": "논문을 찾을 수 없습니다."})

        external_ids = paper.get("externalIds") or {}
        basic = {
            "title": paper.get("title", ""),
            "year": paper.get("year"),
            "venue": paper.get("venue", ""),
            "doi": external_ids.get("DOI"),
            "arxivId": external_ids.get("ArXiv"),
            "citationCount": paper.get("citationCount"),
        }

        abstract = paper.get("abstract") or ""
        analysis = analyze_paper(abstract, title=basic["title"], doi=basic["doi"] or "")
        authors = enrich_authors(paper)
        quality = lookup_venue(basic["venue"])

        return JSONResponse({
            "basic": basic,
            "analysis": analysis,
            "authors": authors,
            "quality": quality,
        })

    except Exception as e:
        return JSONResponse({"error": str(e)})


@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    try:
        from core.pdf_extractor import extract_from_pdf

        pdf_bytes = await file.read()
        extracted = extract_from_pdf(pdf_bytes)

        title    = extracted.get("title", "")
        abstract = extracted.get("abstract", "")
        doi      = extracted.get("doi") or ""
        arxiv_id = extracted.get("arxivId")
        figures  = extracted.get("figures", [])

        # Try to enrich from Semantic Scholar
        paper = None
        venue = ""
        year = None
        citation_count = None
        authors = []

        if arxiv_id:
            try:
                paper = fetch_paper_by_url(f"https://arxiv.org/abs/{arxiv_id}")
            except Exception:
                pass
        if not paper and doi:
            try:
                paper = fetch_paper_by_url(f"https://doi.org/{doi}")
            except Exception:
                pass

        if paper:
            ext = paper.get("externalIds") or {}
            title         = paper.get("title") or title
            abstract      = paper.get("abstract") or abstract
            doi           = ext.get("DOI") or doi
            arxiv_id      = ext.get("ArXiv") or arxiv_id
            venue         = paper.get("venue", "")
            year          = paper.get("year")
            citation_count = paper.get("citationCount")
            authors       = enrich_authors(paper)

        basic = {
            "title": title,
            "year": year,
            "venue": venue,
            "doi": doi or None,
            "arxivId": arxiv_id,
            "citationCount": citation_count,
        }

        analysis = analyze_paper(abstract, title=title, doi=doi)
        quality  = lookup_venue(venue)

        return JSONResponse({
            "basic": basic,
            "analysis": analysis,
            "authors": authors,
            "quality": quality,
            "figures": figures,
        })

    except Exception as e:
        return JSONResponse({"error": str(e)})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
