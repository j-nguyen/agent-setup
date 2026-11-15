def search_products(products: list[dict], query: str, case_sensitive: bool = True) -> list[dict]:
    """Return products whose name or code contains `query`.

    Case-sensitive by default on purpose: product codes are case-significant
    (see README "Search"). Use case_sensitive=False for a case-insensitive match.
    """
    if case_sensitive:
        return [p for p in products if query in p["name"] or query in p["code"]]
    q = query.casefold()
    return [p for p in products if q in p["name"].casefold() or q in p["code"].casefold()]
