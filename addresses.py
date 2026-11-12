import re
from typing import Optional

_PATTERNS = [
    re.compile(r"0x[a-fA-F0-9]{40}"),                              # EVM (ERC20 / BEP20 / Polygon ...)
    re.compile(r"T[1-9A-HJ-NP-Za-km-z]{33}"),                      # TRON (TRC20)
    re.compile(r"(?:bc1|ltc1)[a-z0-9]{25,62}"),                    # BTC / LTC bech32
    re.compile(r"[13LM][a-km-zA-HJ-NP-Z1-9]{25,34}"),              # BTC / LTC legacy
    re.compile(r"(?:EQ|UQ)[A-Za-z0-9_-]{46}"),                     # TON
    re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}"),                    # Solana
    re.compile(r"[A-Za-z0-9.\-_]{2,256}@[A-Za-z]{2,64}"),          # UPI ID
]


def find_address(text: Optional[str]) -> Optional[str]:
    """Return the address if the message is a single wallet address / UPI ID."""
    token = (text or "").strip().strip("`")
    if not token or any(c.isspace() for c in token):
        return None
    for rx in _PATTERNS:
        if rx.fullmatch(token):
            return token
    return None


def normalize(address: str) -> str:
    return address.lower() if address.startswith("0x") or "@" in address else address


NETWORK_PATTERNS = {
    "BEP20": _PATTERNS[0],
    "TRC20": _PATTERNS[1],
}
