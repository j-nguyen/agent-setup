# Emails the finalized invoice PDF to the account's billing address.
class DeliverInvoiceJob
  include Sidekiq::Job
  sidekiq_options queue: "mailers", retry: 10

  def perform(invoice_id)
    invoice = Invoice.find_by(id: invoice_id)
    return if invoice.nil? # deleted since it was enqueued

    InvoiceMailer.finalized(invoice).deliver_now
    invoice.update!(emailed_at: Time.current)
  end
end
