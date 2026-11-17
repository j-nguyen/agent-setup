// All recurring jobs are registered here at startup.
import { sendWeeklyReports } from "../email/weeklyReport.ts";
import { deleteOlderThan } from "../notifications/repo.ts";
import { registerJob } from "./index.ts";

const NOTIFICATION_RETENTION_DAYS = 90;

export function registerAllJobs(): void {
  // Plan D4 / C8: notifications are kept for 90 days.
  registerJob({
    name: "notifications.retention",
    schedule: { dailyAt: "03:15" },
    run: (now) => {
      const cutoff = new Date(now.getTime() - NOTIFICATION_RETENTION_DAYS * 86_400_000);
      deleteOlderThan(cutoff);
    },
  });

  registerJob({
    name: "email.weekly-report",
    schedule: { weeklyAt: { day: 1, time: "07:00" } },
    run: async (now) => {
      await sendWeeklyReports(now);
    },
  });
}
