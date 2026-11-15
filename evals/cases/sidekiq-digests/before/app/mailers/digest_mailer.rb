class DigestMailer < ApplicationMailer
  def weekly(user, week)
    @user, @week = user, week
    @items = ActivityFeed.new(user).for_week(Date.iso8601(week))
    mail(to: user.email, subject: "Your week on Acme")
  end
end
