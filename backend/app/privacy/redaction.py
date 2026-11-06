"""
Best-effort masking of personal data in text, applied before anything is
stored or sent to the judge. It catches common patterns. It is NOT a
guarantee: anything it misses is still stored, so agents should avoid sending
raw personal data in the first place.
"""
import re
from dataclasses import dataclass, field

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CNIC = re.compile(r"(?<!\d)\d{5}-\d{7}-\d(?!\d)")            # Pakistan national ID
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")          # US social security number
CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
PHONE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


@dataclass
class RedactionResult:
    text: str
    counts: dict = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.counts)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _luhn_ok(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _is_card(candidate: str) -> bool:
    digits = _digits(candidate)
    return 13 <= len(digits) <= 19 and _luhn_ok(digits)


def _is_phone(candidate: str) -> bool:
    return 9 <= len(_digits(candidate)) <= 15


def _replace(pattern, label, text, counts, accept=lambda match: True):
    def substitute(match):
        if not accept(match):
            return match.group(0)
        counts[label] = counts.get(label, 0) + 1
        return f"[{label}]"

    return pattern.sub(substitute, text)


def redact(text: str | None) -> RedactionResult:
    if not text:
        return RedactionResult(text="")
    counts: dict = {}
    out = _replace(EMAIL, "EMAIL", text, counts)
    out = _replace(CNIC, "CNIC", out, counts)
    out = _replace(SSN, "SSN", out, counts)
    out = _replace(CARD_CANDIDATE, "CARD", out, counts,
                   accept=lambda m: _is_card(m.group(0)))
    out = _replace(PHONE, "PHONE", out, counts,
                   accept=lambda m: _is_phone(m.group(0)))
    return RedactionResult(text=out, counts=counts)
