class User < ApplicationRecord
  # Columns: email, name, digest_opt_in (boolean, default false), time_zone
  has_many :weekly_digests, dependent: :delete_all

  # after_create_commit, not after_create: the job must never run before the row is committed.
  after_create_commit { WelcomeEmailJob.perform_async(id) }
end
