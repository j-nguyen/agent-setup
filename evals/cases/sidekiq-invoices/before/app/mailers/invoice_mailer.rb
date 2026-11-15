class InvoiceMailer < ApplicationMailer
  def finalized(invoice)
    @invoice = invoice
    attachments["invoice-#{invoice.number}.pdf"] = InvoicePdf.new(invoice).render
    mail(to: invoice.billing_email, subject: "Invoice #{invoice.number}")
  end
end
