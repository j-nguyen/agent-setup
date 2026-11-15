class WelcomeEmailJob
  include Sidekiq::Job
  sidekiq_options queue: "mailers", retry: 5

  def perform(user_id)
    user = User.find_by(id: user_id)
    return if user.nil? # deleted before we got to it

    UserMailer.welcome(user).deliver_now
  end
end
