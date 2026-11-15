# Client for the accounting ledger API.
class LedgerClient
  def initialize(conn: Faraday.new(url: ENV.fetch("LEDGER_URL")) { |f| f.request :json; f.response :raise_error })
    @conn = conn
  end

  # Creates a ledger entry. With the same idempotency_key the ledger returns the
  # existing entry instead of creating a second one (keys are kept for 30 days).
  def create_entry(external_id:, amount_cents:, currency:, booked_at:, idempotency_key: nil)
    headers = idempotency_key ? { "Idempotency-Key" => idempotency_key } : {}
    @conn.post("/v1/entries", { external_id:, amount_cents:, currency:, booked_at: booked_at.iso8601 }, headers)
  end
end
