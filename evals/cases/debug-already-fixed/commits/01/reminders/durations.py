import re

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_DURATION = re.compile(r"^(\d+)([smhd])$")


def parse_duration(text: str) -> int:
    """Parse '90s', '5m', '2h' or '1d' into seconds."""
    m = _DURATION.match(text.strip())
    if not m:
        raise ValueError(f"invalid duration {text!r}")
    return int(m.group(1)) * _UNIT_SECONDS[m.group(2)]
