import re
import base64
import fitz  # pymupdf

_ARXIV_RE = re.compile(r'arXiv\s*[:\.]?\s*([\d]{4}\.\d{4,5}(?:v\d+)?)', re.I)
_DOI_RE   = re.compile(r'10\.\d{4,}/[^\s&?#"\']+')


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


_NEXT_SECTION = re.compile(
    r'\n\s*(?:(?:1\s*\.?\s*)?(?:introduction|keywords|index terms|ccs concepts|'
    r'background|related work|notation|nomenclature))',
    re.I
)

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
        # Strategy 3: just grab text after the word Abstract up to 1500 chars
        m = re.search(r'(?:abstract|ABSTRACT)[^\w]+([\s\S]{100,1500}?)(?=' + _NEXT_SECTION.pattern + r'|\Z)',
                      text, re.I)

    if m:
        abstract = m.group(1).strip()
        abstract = re.sub(r'-\s*\n', '', abstract)   # de-hyphenate
        abstract = re.sub(r'\s+', ' ', abstract)
        # sanity: must be at least 80 chars and not another section header
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


_FIG_CAPTION_RE = re.compile(r'\bfig(?:ure)?\.?\s*\d+', re.I)


def _find_figure_rects(page: fitz.Page) -> list:
    """Return bounding boxes of blocks that contain figure captions."""
    rects = []
    blocks = page.get_text("dict")["blocks"]
    page_h = page.rect.height
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_text = " ".join(s.get("text", "") for s in line.get("spans", []))
            if _FIG_CAPTION_RE.search(line_text):
                rects.append(fitz.Rect(block["bbox"]))
                break
    return rects


def extract_figures(doc: fitz.Document, max_figures: int = 3) -> list:
    candidates = []

    for page_num in range(min(len(doc), 12)):
        page = doc[page_num]
        page_area = page.rect.width * page.rect.height
        caption_rects = _find_figure_rects(page)

        img_list = page.get_images(full=True)
        for img in img_list:
            xref = img[0]
            try:
                # get image placement rect on page
                img_rects = page.get_image_rects(xref)
                if not img_rects:
                    continue
                img_rect = img_rects[0]

                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                w, h = pix.width, pix.height

                # skip tiny or very narrow/tall decorative images
                if w < 200 or h < 150:
                    pix = None
                    continue
                aspect = w / h
                if aspect < 0.4 or aspect > 6:
                    pix = None
                    continue

                # skip images that are too small relative to the page (likely icons)
                img_area = img_rect.width * img_rect.height
                if img_area < page_area * 0.03:
                    pix = None
                    continue

                # score: boost if a caption is nearby (within 80pt vertically)
                score = w * h
                for cr in caption_rects:
                    gap = min(abs(img_rect.y1 - cr.y0), abs(cr.y1 - img_rect.y0))
                    if gap < 80:
                        score *= 10
                        break

                b64 = base64.b64encode(pix.tobytes("png")).decode()
                candidates.append({
                    "page": page_num + 1,
                    "width": w,
                    "height": h,
                    "score": score,
                    "data": f"data:image/png;base64,{b64}",
                })
                pix = None
            except Exception:
                continue

    candidates.sort(key=lambda x: -x["score"])
    for c in candidates:
        del c["score"]
    return candidates[:max_figures]


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
