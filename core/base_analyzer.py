import json

PROMPT_TEMPLATE = """다음은 논문의 초록입니다.

[초록]
{abstract}

아래 항목을 한국어로 작성하세요. 초록에 직접 언급되지 않더라도 내용을 바탕으로 합리적으로 추론해도 됩니다.

다음 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "keywords": ["핵심 키워드 3~5개 (영문 또는 한문 혼용 가능)"],
  "problem_short": "해결하려는 문제 한 줄 요약",
  "problem": "기존 방법의 한계와 배경 (2~3문장)",
  "method_short": "제안 방법 한 줄 요약",
  "method": "핵심 아이디어 및 방법론 (2~3문장, 구체적 기술 요소 포함)",
  "conclusion_short": "주요 결론 한 줄 요약",
  "conclusion": "주요 결론 및 기여 (2~3문장, 성능 수치·비교 실험·의의 포함)",
  "relevance": "높음 또는 낮음 또는 부분적",
  "relevance_reason": "ECG / 시간-주파수 변환 / Vision Transformer 관련 근거 한 줄"
}}"""

EMPTY_RESULT = {
    "keywords": [],
    "problem_short": "초록 없음",
    "problem": "초록 없음",
    "method_short": "초록 없음",
    "method": "초록 없음",
    "conclusion_short": "초록 없음",
    "conclusion": "초록 없음",
    "relevance": "알 수 없음",
    "relevance_reason": "초록이 제공되지 않았습니다.",
}


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def build_prompt(abstract: str) -> str:
    return PROMPT_TEMPLATE.format(abstract=abstract)
