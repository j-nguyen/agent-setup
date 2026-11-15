ActiveRecord::Schema[7.2].define(version: 2026_10_01_000000) do
  create_table "users", force: :cascade do |t|
    t.string "email", null: false
    t.string "name", null: false
    t.boolean "digest_opt_in", default: false, null: false
    t.string "time_zone", default: "UTC", null: false
    t.timestamps
    t.index ["email"], unique: true
    t.index ["digest_opt_in"], where: "digest_opt_in"
  end
end
