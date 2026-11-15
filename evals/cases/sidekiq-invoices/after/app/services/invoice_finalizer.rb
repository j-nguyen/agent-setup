class InvoiceFinalizer
  def initialize(invoice)
    @invoice = invoice
  end

  def call
    Invoice.transaction do
      @invoice.lock!
      raise ArgumentError, "invoice #{@invoice.id} is not a draft" unless @invoice.draft?

      @invoice.update!(
        status: :finalized,
        total_cents: @invoice.line_items.sum(:amount_cents),
        finalized_at: Time.current,
      )

      DeliverInvoiceJob.perform_async(@invoice.id)
      SyncInvoiceToLedgerJob.perform_async(@invoice.id, @invoice.finalized_at)
    end
    @invoice
  end
end
