class CreateWeeklyDigests < ActiveRecord::Migration[7.2]
  def change
    create_table :weekly_digests do |t|
      t.references :user, null: false, foreign_key: true, index: false
      t.string :week, null: false # ISO date of the week's Monday, e.g. "2026-11-09"
      t.string :claim_token # set while a job is sending; see SendDigestJob
      t.datetime :claimed_at
      t.datetime :sent_at
      t.timestamps
    end
    # One digest per user per week; also serves lookups by user_id.
    add_index :weekly_digests, [:user_id, :week], unique: true
  end
end
