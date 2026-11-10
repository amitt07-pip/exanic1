import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

_SEP = r"[-:–—=]"
_MUST = r"(?:\[\s*must\s*\]\s*)?"
_LABELS = {
    "seller": r"seller",
    "buyer": r"buyer",
    "amount": r"amount",
    "method": r"payment\s*method",
    "fee_by": r"fees?\s*by",
}
_LINE_RE = {
    key: re.compile(rf"^\s*{_MUST}{label}\b[^\n]*?{_SEP}\s*(.*)$", re.IGNORECASE)
    for key, label in _LABELS.items()
}
_TERMS_RE = re.compile(rf"^\s*{_MUST}terms\b[^\n]*?{_SEP}\s*(.*)$", re.IGNORECASE)
_USERNAME_RE = re.compile(r"@([A-Za-z0-9_]{4,32})")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class DealForm:
    seller: str
    buyer: str
    amount: Decimal
    method: str
    fee_by: str
    terms: str


def parse_number(text: str) -> Optional[Decimal]:
    m = _NUMBER_RE.search(text.replace(",", ""))
    if not m:
        return None
    try:
        value = Decimal(m.group(0))
    except InvalidOperation:
        return None
    return value if value > 0 else None


def parse_form(text: Optional[str]) -> tuple[Optional[DealForm], list[str]]:
    """Returns (form, problems). form is None when any required field is missing/invalid."""
    values: dict[str, str] = {}
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        tm = _TERMS_RE.match(line)
        if tm:
            rest = [tm.group(1).strip(), *[l.strip() for l in lines[i + 1:]]]
            values["terms"] = "\n".join(x for x in rest if x).strip()
            break
        for key, rx in _LINE_RE.items():
            if key not in values:
                m = rx.match(line)
                if m:
                    values[key] = m.group(1).strip()
                    break

    problems = []
    seller = _USERNAME_RE.search(values.get("seller", ""))
    buyer = _USERNAME_RE.search(values.get("buyer", ""))
    amount = parse_number(values.get("amount", ""))
    method = values.get("method", "").strip()
    fee_by = values.get("fee_by", "").strip().lower()
    if not seller:
        problems.append("Seller (@username)")
    if not buyer:
        problems.append("Buyer (@username)")
    if not amount:
        problems.append("Amount in $")
    if not method:
        problems.append("Payment Method")
    if fee_by not in ("buyer", "seller"):
        problems.append("Fee By (Buyer or Seller)")
    if problems:
        return None, problems
    return DealForm(
        seller=seller.group(1),
        buyer=buyer.group(1),
        amount=amount,
        method=method,
        fee_by=fee_by.capitalize(),
        terms=values.get("terms", ""),
    ), []


def fmt_amount(value: Decimal) -> str:
    """100 -> 100.0, 100.50 -> 100.5, 99.25 -> 99.25"""
    text = format(value.normalize(), "f")
    return text if "." in text else f"{text}.0"


_STAT_SEP = r"\s*[:\-–—=]\s*"
_STAT_NUM = r"\$?\s*([\d,]+(?:\.\d+)?)"
_STAT_RES = {
    "total": re.compile(rf"total\s*escrows?{_STAT_SEP}([\d,]+)", re.IGNORECASE),
    "worth": re.compile(rf"escrowed\s*amount{_STAT_SEP}{_STAT_NUM}", re.IGNORECASE),
    "largest": re.compile(rf"largest\s*deal{_STAT_SEP}{_STAT_NUM}", re.IGNORECASE),
    "rank": re.compile(rf"rank{_STAT_SEP}#?\s*([\d,]+)", re.IGNORECASE),
    "rate": re.compile(rf"success\s*rate{_STAT_SEP}(\d+(?:\.\d+)?)", re.IGNORECASE),
}
STAT_LABELS = {
    "total": "Total Escrows", "worth": "Escrowed Amount", "largest": "Largest Deal",
    "rank": "Rank", "rate": "Success Rate",
}


def parse_stats(text: Optional[str]) -> tuple[dict, list[str]]:
    """Returns (values, missing/invalid labels)."""
    found: dict[str, str] = {}
    for line in (text or "").splitlines():
        for key, rx in _STAT_RES.items():
            if key not in found:
                m = rx.search(line)
                if m:
                    found[key] = m.group(1).replace(",", "")
    values: dict = {}
    for key, raw in found.items():
        values[key] = int(raw) if key in ("total", "rank") else float(raw)
    bad = [label for key, label in STAT_LABELS.items() if key not in values]
    if values.get("rank", 1) < 1:
        bad.append(STAT_LABELS["rank"])
    if values.get("rate", 0) > 100:
        bad.append(STAT_LABELS["rate"])
    return values, bad
