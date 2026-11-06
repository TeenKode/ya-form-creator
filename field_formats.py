"""Advisory local format checks; Yandex is authoritative for native validators."""
import re
from urllib.parse import urlsplit


def format_error(kind: str, value: str) -> str | None:
    """Never coerce identifiers to numbers or rewrite the user's answer."""
    if kind in ("plain", "full_name"):
        return None
    if kind == "email":
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            return "укажите почту в формате name@example.org."
    elif kind == "phone":
        digits = re.sub(r"[ ()-]", "", value)
        if not re.fullmatch(r"(?:\+7|8)[0-9]{10}", digits):
            return "укажите телефон РФ: +7 и 10 цифр либо 8 и 10 цифр."
    elif kind == "url":
        try:
            parsed = urlsplit(value)
            valid = parsed.scheme in ("http", "https") and bool(parsed.hostname) and not any(c.isspace() for c in value)
            parsed.port  # Reject malformed or out-of-range ports.
        except ValueError:
            valid = False
        if not valid:
            return "укажите полную ссылку, начинающуюся с https:// или http://."
    elif kind == "inn":
        if not re.fullmatch(r"[0-9]{10}|[0-9]{12}", value):
            return "ИНН должен содержать 10 или 12 цифр."
        digits = [int(c) for c in value]
        def checksum(weights):
            return sum(a*b for a, b in zip(digits, weights)) % 11 % 10
        if len(value) == 10:
            valid = checksum([2, 4, 10, 3, 5, 9, 4, 6, 8]) == digits[9]
        else:
            valid = (checksum([7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == digits[10]
                     and checksum([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]) == digits[11])
        if not valid:
            return "проверьте контрольные цифры ИНН."
    elif kind == "decimal":
        if not re.fullmatch(r"[+-]?[0-9]+(?:[.,][0-9]+)?", value):
            return "укажите число, например 12,5."
    return None
