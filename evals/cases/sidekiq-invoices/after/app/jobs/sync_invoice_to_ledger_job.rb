# Books a finalized invoice in the accounting ledger.
class SyncInvoiceToLedgerJob
  include Sidekiq::Job
  sidekiq_options queue: "default", retry: 25

  sidekiq_retries_exhausted do |job, ex|
    Rails.logger.error("ledger sync gave up for invoice #{job["args"].first}: #{ex.message}")
  end

  def perform(invoice_id, booked_at)
    invoice = Invoice.find(invoice_id)
    LedgerClient.new.create_entry(
      external_id: "invoice-#{invoice.id}",
      amount_cents: invoice.total_cents,
      currency: invoice.currency,
      booked_at: booked_at,
    )
  end
end
