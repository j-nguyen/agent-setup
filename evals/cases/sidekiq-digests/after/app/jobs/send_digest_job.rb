# Sends one user's weekly digest. Safe to retry and to enqueue twice: the
# (user_id, week) row is claimed with one atomic UPDATE, and the email is sent
# outside any transaction, so no row lock is held while talking to SMTP.
class SendDigestJob
  include Sidekiq::Job
  sidekiq_options queue: "mailers", retry: 8

  # Another job holds the claim and hasn't marked the digest sent yet. Raising makes
  # Sidekiq retry later, when the digest is either sent or its claim has expired.
  class InFlight < StandardError; end

  # A claim is normally released on failure (see ensure below); the TTL only matters
  # when a worker is killed outright. It is far longer than a send can take, since
  # SMTP delivery has 10 s open/read timeouts.
  CLAIM_TTL = 5.minutes

  def perform(user_id, week)
    user = User.find_by(id: user_id)
    return if user.nil? || !user.digest_opt_in

    # create_or_find_by! inserts first and falls back to a lookup on the unique
    # index, so two concurrent jobs end up with the same row instead of racing.
    digest = WeeklyDigest.create_or_find_by!(user_id: user.id, week: week)
    now = Time.current
    token = SecureRandom.uuid
    claimed = WeeklyDigest.where(id: digest.id, sent_at: nil)
                          .where("claimed_at IS NULL OR claimed_at < ?", now - CLAIM_TTL)
                          .update_all(claim_token: token, claimed_at: now, updated_at: now)
    if claimed.zero?
      return if digest.reload.sent_at

      raise InFlight, "digest #{digest.id} is being sent by another job"
    end

    # Only ever touch the row while it still holds our claim, never another job's.
    mine = WeeklyDigest.where(id: digest.id, claim_token: token)
    sent = false
    begin
      DigestMailer.weekly(user, week).deliver_now
      sent = true
    ensure
      # Also runs on Sidekiq::Shutdown (an Interrupt, not a StandardError) during
      # deploys, so the re-queued job can claim the digest again.
      mine.update_all(claim_token: nil, claimed_at: nil) unless sent
    end
    mine.update_all(sent_at: Time.current, updated_at: Time.current)
  end
end
