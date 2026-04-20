import os
import anthropic
from .base_analyzer import EMPTY_RESULT, build_prompt, parse_json_response


def analyze_paper(abstract: str) -> dict:
    if not abstract:
        return EMPTY_RESULT

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": build_prompt(abstract)}],
    )
    return parse_json_response(message.content[0].text)
