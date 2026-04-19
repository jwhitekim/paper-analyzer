import os


def analyze_paper(abstract: str, title: str = "", doi: str = "") -> dict:
    """Route to Claude or Gemini based on LLM_PROVIDER env var (default: gemini)."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "claude":
        from .claude_analyzer import analyze_paper as _analyze
        return _analyze(abstract)
    else:
        from .gemini_analyzer import analyze_paper as _analyze
        return _analyze(abstract, title=title, doi=doi)


def current_provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini").lower()
