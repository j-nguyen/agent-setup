"""Contacts CSV export."""
import csv
import io

COLUMNS = ["name", "email"]


def export_contacts(contacts: list[dict]) -> bytes:
    """Return the export file's bytes.

    Encoded as UTF-8 *with* a byte-order mark (utf-8-sig) so that Excel on Windows
    detects the encoding instead of falling back to the legacy code page.
    """
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(contacts)
    return buf.getvalue().encode("utf-8-sig")
