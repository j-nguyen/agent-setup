// Weekly team report email: the existing example of a list-based recurring email.
import { activeUsers } from "../users/users.ts";
import { sendEmail } from "./mailer.ts";

export async function sendWeeklyReports(now: Date): Promise<number> {
  let n = 0;
  for (const u of activeUsers()) {
    await sendEmail({
      to: u.email,
      subject: `Your week on teamboard (${now.toISOString().slice(0, 10)})`,
      text: `Hi ${u.name}, here is your weekly report.`,
      html: `<p>Hi ${u.name}, here is your weekly report.</p>`,
      list: { userId: u.id, name: "weekly-report" },
    });
    n += 1;
  }
  return n;
}
