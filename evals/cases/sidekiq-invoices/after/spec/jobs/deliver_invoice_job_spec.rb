require "rails_helper"
require "sidekiq/testing"

RSpec.describe DeliverInvoiceJob do
  it "emails the invoice and records when" do
    invoice = create(:invoice, :finalized)
    expect { described_class.new.perform(invoice.id) }
      .to change { ActionMailer::Base.deliveries.size }.by(1)
    expect(invoice.reload.emailed_at).to be_present
  end

  it "does nothing for a deleted invoice" do
    expect { described_class.new.perform(-1) }.not_to raise_error
  end
end
