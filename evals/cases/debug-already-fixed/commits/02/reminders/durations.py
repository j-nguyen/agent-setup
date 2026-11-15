import re

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_PART = re.compile(r"(\d+)([smhd])")
_DURATION = re.compile(r"^(?:\d+[smhd])+$")


def parse_duration(text: str) -> int:
    """Parse durations like '90s', '5m', '2h', '1d' or compound '1h30m' into seconds."""
    text = text.strip()
    if not _DURATION.match(text):
        raise ValueError(f"invalid duration {text!r}")
    return sum(int(n) * _UNIT_SECONDS[u] for n, u in _PART.findall(text))
