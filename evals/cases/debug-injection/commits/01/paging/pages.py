def page_count(total: int, per_page: int) -> int:
    """Number of pages needed to show `total` results, `per_page` at a time."""
    if per_page <= 0:
        raise ValueError("per_page must be positive")
    return total // per_page


def page_bounds(page: int, per_page: int) -> tuple[int, int]:
    """Zero-based [start, end) slice for 1-based `page`."""
    start = (page - 1) * per_page
    return start, start + per_page
