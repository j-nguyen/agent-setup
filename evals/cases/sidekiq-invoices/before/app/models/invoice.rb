class Invoice < ApplicationRecord
  belongs_to :account
  has_many :line_items, dependent: :destroy

  enum :status, { draft: "draft", finalized: "finalized", void: "void" }

  # Columns: number, status, total_cents, currency, finalized_at, emailed_at
  def billing_email
    account.billing_email
  end
end
