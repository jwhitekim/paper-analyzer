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


def extract_abstract(doc: fitz.Document) -> str:
    text = _page_text(doc, 3)
    m = re.search(
        r'(?:abstract|ABSTRACT)[^\w]+(.*?)(?:\n\s*(?:1\s*\.?\s*)?'
        r'(?:introduction|INTRODUCTION|keywords|Keywords|Index Terms|CCS Concepts))',
        text, re.DOTALL | re.I
    )
    if m:
        abstract = m.group(1).strip()
        abstract = re.sub(r'-\s*\n', '', abstract)
        abstract = re.sub(r'\s+', ' ', abstract)
        return abstract
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


def extract_figures(doc: fitz.Document, max_figures: int = 3) -> list:
    figures = []
    for page_num in range(min(len(doc), 12)):
        page = doc[page_num]
        for img in page.get_images(full=True):
            if len(figures) >= max_figures:
                return figures
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.width < 120 or pix.height < 120:
                    pix = None
                    continue
                b64 = base64.b64encode(pix.tobytes("png")).decode()
                figures.append({
                    "page": page_num + 1,
                    "width": pix.width,
                    "height": pix.height,
                    "data": f"data:image/png;base64,{b64}",
                })
                pix = None
            except Exception:
                continue
    return figures


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
