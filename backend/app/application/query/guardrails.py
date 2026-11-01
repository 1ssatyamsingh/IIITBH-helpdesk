import re

MAX_QUERY_LENGTH = 1200
INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"reveal\s+(the\s+)?(system|developer)\s+prompt",
    r"show\s+(me\s+)?(the\s+)?(system|developer)\s+prompt",
    r"print\s+(all\s+)?(api|secret|access)\s+keys",
    r"exfiltrat(e|ion)\s+(data|secrets|credentials)",
    r"bypass\s+(the\s+)?(safety|security|guardrails|policy)",
    r"override\s+(all\s+)?(safety|security|system)\s+(rules|instructions)",
    r"act\s+as\s+(an?\s+)?(unrestricted|unfiltered|jailbroken)",
    r"developer\s+mode\s+(enabled|on)",
)
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9_-]{16,})\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class QueryGuardrailError(ValueError):
    pass


def validate_question(question: str) -> str:
    if not isinstance(question, str):
        raise QueryGuardrailError("Question must be plain text.")
    clean = " ".join(question.split())
    if not clean:
        raise QueryGuardrailError("Please enter a question.")
    if len(clean) > MAX_QUERY_LENGTH:
        raise QueryGuardrailError(
            f"Question is too long. Keep it under {MAX_QUERY_LENGTH} characters."
        )
    if any(ord(char) < 32 and char not in "\t" for char in clean):
        raise QueryGuardrailError("Question contains unsupported control characters.")
    if any(re.search(pattern, clean, re.IGNORECASE) for pattern in INJECTION_PATTERNS):
        raise QueryGuardrailError(
            "I can help with IIIT Bhagalpur information, but I cannot override system safeguards or reveal hidden instructions and credentials."
        )
    return clean


def sanitize_answer(answer: str) -> str:
    safe = answer
    for pattern in SECRET_PATTERNS:
        safe = pattern.sub("[REDACTED SECRET]", safe)
    return safe
