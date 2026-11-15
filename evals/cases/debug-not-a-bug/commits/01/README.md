# catalog

Run the tests with:

    python3 -m unittest discover -s tests -t .

## Search

`search_products(query)` matches **exact, case-sensitive substrings** by default,
because catalog codes such as `SKU-aB12` and `SKU-Ab12` are different products.
Pass `case_sensitive=False` (the UI's "Ignore case" checkbox) for a case-insensitive search.
