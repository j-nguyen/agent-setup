require "rails_helper"

RSpec.describe SendDigestJob do
  let(:user) { create(:user, digest_opt_in: true) }
  let(:week) { "2026-11-09" }

  it "sends the digest once, even if the job runs twice" do
    expect {
      2.times { described_class.new.perform(user.id, week) }
    }.to change { ActionMailer::Base.deliveries.size }.by(1)
    expect(user.weekly_digests.find_by(week:).sent_at).to be_present
  end

  it "releases the claim when sending fails, so the retry sends it" do
    allow(DigestMailer).to receive(:weekly).and_raise(Net::SMTPServerBusy)
    expect { described_class.new.perform(user.id, week) }.to raise_error(Net::SMTPServerBusy)
    allow(DigestMailer).to receive(:weekly).and_call_original
    expect { described_class.new.perform(user.id, week) }.to change { ActionMailer::Base.deliveries.size }.by(1)
  end

  it "retries later while another job holds the claim" do
    create(:weekly_digest, user:, week:, claimed_at: 1.minute.ago)
    expect { described_class.new.perform(user.id, week) }.to raise_error(SendDigestJob::InFlight)
    expect(ActionMailer::Base.deliveries).to be_empty
  end

  it "takes over a claim that has expired" do
    create(:weekly_digest, user:, week:, claimed_at: 10.minutes.ago)
    expect { described_class.new.perform(user.id, week) }.to change { ActionMailer::Base.deliveries.size }.by(1)
  end

  it "skips users who opted out after the fan-out" do
    user.update!(digest_opt_in: false)
    expect { described_class.new.perform(user.id, week) }.not_to(change { ActionMailer::Base.deliveries.size })
  end
end
