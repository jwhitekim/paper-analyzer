import os
from google import genai
from google.genai import types
from .base_analyzer import EMPTY_RESULT, build_prompt, parse_json_response

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _fetch_abstract_via_search(title: str, doi: str = "") -> str:
    """Gemini + Google Search로 초록 텍스트를 검색해 반환."""
    query = f'"{title}"'
    if doi:
        query += f" DOI:{doi}"

    prompt = (
        f"다음 논문의 영어 초록(abstract) 전문을 찾아서 그대로 출력해줘. "
        f"요약하거나 번역하지 말고 원문 그대로.\n\n논문: {query}"
    )

    client = _get_client()
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        ),
    )
    text = (resp.text or "").strip()
    # 검색 결과가 너무 짧으면 신뢰하지 않음
    return text if len(text) > 100 else ""


def analyze_paper(abstract: str, title: str = "", doi: str = "") -> dict:
    """
    abstract가 있으면 바로 분석.
    없으면 Gemini Google Search로 초록을 먼저 검색한 뒤 분석.
    그래도 없으면 EMPTY_RESULT 반환.
    """
    if not abstract and title:
        abstract = _fetch_abstract_via_search(title, doi)

    if not abstract:
        return {**EMPTY_RESULT, "problem": "초록 미수집 (S2 미인덱스 + 검색 실패)"}

    client = _get_client()
    resp = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=build_prompt(abstract),
        config=types.GenerateContentConfig(temperature=0.1),
    )
    raw = resp.text or ""
    if not raw.strip():
        return {**EMPTY_RESULT, "problem": "Gemini 응답이 비어있습니다. 잠시 후 다시 시도하세요."}
    return parse_json_response(raw)
