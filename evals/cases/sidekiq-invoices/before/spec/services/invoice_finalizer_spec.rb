require "rails_helper"

RSpec.describe InvoiceFinalizer do
  it "finalizes a draft and totals its line items" do
    invoice = create(:invoice, :with_line_items, amounts: [1000, 2500])
    described_class.new(invoice).call
    expect(invoice.reload).to be_finalized
    expect(invoice.total_cents).to eq(3500)
  end
end
