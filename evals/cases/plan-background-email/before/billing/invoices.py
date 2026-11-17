"""Invoices. PDFs are rendered in the background by the jobs worker."""
from __future__ import annotations

from core import db
from jobs import queue
from jobs.handlers import handler


def create_invoice(user_id: int, amount_cents: int) -> int:
    with db.atomic():
        cur = db.execute("INSERT INTO invoices (user_id, amount_cents) VALUES (?, ?)",
                         (user_id, amount_cents))
        invoice_id = cur.lastrowid
        # The job row is written in the same transaction, so it exists only if the invoice does.
        queue.enqueue("invoice.render_pdf", {"invoice_id": invoice_id},
                      dedupe_key=f"invoice.render_pdf:{invoice_id}")
    return invoice_id


@handler("invoice.render_pdf")
def render_pdf(payload: dict) -> None:
    row = db.execute("SELECT pdf_path FROM invoices WHERE id = ?", (payload["invoice_id"],)).fetchone()
    if row is None or row["pdf_path"]:
        return  # deleted, or already rendered by an earlier attempt
    path = f"/var/invoices/{payload['invoice_id']}.pdf"
    # (rendering elided)
    db.execute("UPDATE invoices SET pdf_path = ? WHERE id = ?", (path, payload["invoice_id"]))
