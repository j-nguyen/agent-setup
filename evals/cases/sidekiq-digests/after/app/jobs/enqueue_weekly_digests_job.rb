# Run every Monday 06:00 UTC by the scheduler (`EnqueueWeeklyDigestsJob.perform_async`).
# Fans out one SendDigestJob per opted-in user, in batches.
class EnqueueWeeklyDigestsJob
  include Sidekiq::Job
  sidekiq_options queue: "low", retry: 3

  BATCH_SIZE = 1_000

  def perform(week = Date.current.beginning_of_week.iso8601)
    User.where(digest_opt_in: true).in_batches(of: BATCH_SIZE) do |users|
      SendDigestJob.perform_bulk(users.pluck(:id).map { |id| [id, week] })
    end
  end
end
