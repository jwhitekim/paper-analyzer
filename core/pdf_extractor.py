import re
import base64
import fitz  # pymupdf

_ARXIV_RE = re.compile(r'arXiv\s*[:\.]?\s*([\d]{4}\.\d{4,5}(?:v\d+)?)', re.I)
_DOI_RE   = re.compile(r'10\.\d{4,}/[^\s&?#"\']+')

# 스펙 우선순위
_PRIORITY_HIGH  = re.compile(r'\b(?:architecture|overview|framework|pipeline)\b', re.I)
_PRIORITY_MID   = re.compile(r'\bfig(?:ure)?\.?\s*1\b', re.I)
_CAPTION_RE     = re.compile(r'\bfig(?:ure)?\.?\s*\d+', re.I)

_NEXT_SECTION = re.compile(
    r'\n\s*(?:(?:1\s*\.?\s*)?(?:introduction|keywords|index terms|ccs concepts|'
    r'background|related work|notation|nomenclature))',
    re.I
)


def _page_text(doc: fitz.Document, pages: int = 2) -> str:
    return "".join(doc[i].get_text() for i in range(min(pages, len(doc))))


def extract_title(doc: fitz.Document) -> str:
    page = doc[0]
    spans = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                size = span.get("size", 0)
                if text and size > 10:
                    spans.append((size, text))

    if not spans:
        return ""

    spans.sort(reverse=True)
    max_size = spans[0][0]
    parts = [t for s, t in spans if s >= max_size * 0.88]
    return " ".join(parts[:6]).strip()


def extract_abstract(doc: fitz.Document) -> str:
    text = _page_text(doc, 3)

    # Strategy 1: "Abstract" header → next section
    m = re.search(r'(?:^|\n)\s*(?:abstract|ABSTRACT)\s*\n(.*?)(?=' + _NEXT_SECTION.pattern + r'|\Z)',
                  text, re.DOTALL | re.I)
    if not m:
        # Strategy 2: inline "Abstract—" or "Abstract:" style
        m = re.search(r'(?:abstract|ABSTRACT)\s*[—–:\-]+\s*(.*?)(?=' + _NEXT_SECTION.pattern + r'|\Z)',
                      text, re.DOTALL | re.I)
    if not m:
        # Strategy 3: grab text after "Abstract" up to 1500 chars
        m = re.search(r'(?:abstract|ABSTRACT)[^\w]+([\s\S]{100,1500}?)(?=' + _NEXT_SECTION.pattern + r'|\Z)',
                      text, re.I)

    if m:
        abstract = m.group(1).strip()
        abstract = re.sub(r'-\s*\n', '', abstract)
        abstract = re.sub(r'\s+', ' ', abstract)
        if len(abstract) >= 80:
            return abstract[:3000]
    return ""


def extract_ids(doc: fitz.Document) -> dict:
    text = _page_text(doc, 2)
    arxiv_id = None
    doi = None

    m = _ARXIV_RE.search(text)
    if m:
        arxiv_id = m.group(1)

    m = _DOI_RE.search(text)
    if m:
        doi = m.group(0).rstrip(".")

    return {"arxivId": arxiv_id, "doi": doi}


def _caption_score(caption_text: str, img_area: float) -> int:
    """
    우선순위:
      300 - Architecture/Overview/Framework/Pipeline 포함 캡션
      200 - Fig. 1 / Figure 1
      100 - 기타 Figure 캡션
        0 - 캡션 없음 (크기만 반영)
    """
    if _PRIORITY_HIGH.search(caption_text):
        return 300
    if _PRIORITY_MID.search(caption_text):
        return 200
    if _CAPTION_RE.search(caption_text):
        return 100
    return 0


def _collect_page_captions(page: fitz.Page) -> list:
    """Return list of (rect, text) for blocks containing figure captions."""
    captions = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        block_text = " ".join(
            s.get("text", "")
            for line in block.get("lines", [])
            for s in line.get("spans", [])
        )
        if _CAPTION_RE.search(block_text):
            captions.append((fitz.Rect(block["bbox"]), block_text))
    return captions


def extract_figures(doc: fitz.Document, max_figures: int = 3) -> list:
    candidates = []
    page_area_ref = None

    for page_num in range(min(len(doc), 12)):
        page = doc[page_num]
        page_area = page.rect.width * page.rect.height
        if page_area_ref is None:
            page_area_ref = page_area

        captions = _collect_page_captions(page)

        for img in page.get_images(full=True):
            xref = img[0]
            try:
                img_rects = page.get_image_rects(xref)
                if not img_rects:
                    continue
                img_rect = img_rects[0]

                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                w, h = pix.width, pix.height

                if w < 200 or h < 150:
                    pix = None
                    continue
                aspect = w / h
                if aspect < 0.3 or aspect > 7:
                    pix = None
                    continue
                img_area = img_rect.width * img_rect.height
                if img_area < page_area * 0.03:
                    pix = None
                    continue

                # 가장 가까운 캡션 찾기 (80pt 이내)
                nearest_caption = ""
                min_gap = float("inf")
                for cr, ct in captions:
                    gap = min(abs(img_rect.y1 - cr.y0), abs(cr.y1 - img_rect.y0))
                    if gap < 80 and gap < min_gap:
                        min_gap = gap
                        nearest_caption = ct

                priority = _caption_score(nearest_caption, img_area)
                # 같은 priority 내에서는 크기 순
                size_score = w * h

                b64 = base64.b64encode(pix.tobytes("png")).decode()
                candidates.append({
                    "page": page_num + 1,
                    "width": w,
                    "height": h,
                    "caption": nearest_caption.strip(),
                    "priority": priority,
                    "size_score": size_score,
                    "data": f"data:image/png;base64,{b64}",
                })
                pix = None
            except Exception:
                continue

    # 우선순위 → 크기 순 정렬
    candidates.sort(key=lambda x: (-x["priority"], -x["size_score"]))

    result = []
    for c in candidates[:max_figures]:
        result.append({
            "page": c["page"],
            "width": c["width"],
            "height": c["height"],
            "caption": c["caption"],
            "data": c["data"],
        })
    return result


def extract_from_pdf(pdf_bytes: bytes) -> dict:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    result = {
        "title": extract_title(doc),
        "abstract": extract_abstract(doc),
        **extract_ids(doc),
        "figures": extract_figures(doc),
    }
    doc.close()
    return result
