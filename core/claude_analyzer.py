import os
import anthropic
from .base_analyzer import EMPTY_RESULT, build_prompt, parse_json_response

_TITLE_PROMPT = """다음 논문의 제목만 주어집니다. 제목에서 유추 가능한 내용을 바탕으로 분석하세요.
초록이 없으므로 제목으로부터 합리적으로 추론하되, 불확실한 부분은 솔직히 표현하세요.

논문 제목: {title}
DOI: {doi}

""" + """다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "keywords": ["핵심 키워드 3~5개"],
  "problem_short": "해결하려는 문제 한 줄 요약",
  "problem": "제목 기반으로 추정되는 문제 (2~3문장, 추론임을 명시)",
  "method_short": "제안 방법 한 줄 요약",
  "method": "제목 기반으로 추정되는 방법론 (2~3문장, 추론임을 명시)",
  "conclusion_short": "주요 결론 한 줄 요약",
  "conclusion": "제목 기반으로 추정되는 기여 (2~3문장, 추론임을 명시)",
  "relevance": "높음 또는 낮음 또는 부분적",
  "relevance_reason": "ECG / 시간-주파수 변환 / Vision Transformer 관련 근거 한 줄"
}}"""


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def analyze_paper(abstract: str, title: str = "", doi: str = "") -> dict:
    if not abstract and not title:
        return EMPTY_RESULT

    client = _get_client()

    if abstract:
        prompt = build_prompt(abstract)
    else:
        prompt = _TITLE_PROMPT.format(title=title, doi=doi or "없음")

    message = client.messages.create(
        model=os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text
    if not raw or not raw.strip():
        return {**EMPTY_RESULT, "problem": "Claude 응답이 비어있습니다. 잠시 후 다시 시도하세요."}
    return parse_json_response(raw)
