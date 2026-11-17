// Tiny in-process scheduler. Jobs declare when they run; tick() is called once a
// minute by the server (and directly by tests with a fake clock).
//
// Schedules:
//   { every: "minute" | "hour" }
//   { dailyAt: "HH:MM" }                  - in UTC
//   { weeklyAt: { day: 0-6, time: "HH:MM" } } - day 0 = Sunday, UTC
//
// A job runs at most once per matching minute; lastRun is persisted in the
// job_runs table so a restart doesn't double-run.
import { Table } from "../db.ts";

export type Schedule =
  | { every: "minute" | "hour" }
  | { dailyAt: string }
  | { weeklyAt: { day: number; time: string } };

export type Job = {
  name: string;
  schedule: Schedule;
  run: (now: Date) => Promise<void> | void;
};

type JobRun = { id: string; lastRunMinute: string };
export const jobRuns = new Table<JobRun>();

const jobs = new Map<string, Job>();

export function registerJob(job: Job): void {
  if (jobs.has(job.name)) throw new Error(`job ${job.name} already registered`);
  jobs.set(job.name, job);
}

export function registeredJobs(): string[] {
  return [...jobs.keys()];
}

export function resetJobs(): void {
  jobs.clear();
  jobRuns.clear();
}

function hhmm(d: Date): string {
  return d.toISOString().slice(11, 16);
}

export function isDue(s: Schedule, now: Date): boolean {
  if ("every" in s) return s.every === "minute" || now.getUTCMinutes() === 0;
  if ("dailyAt" in s) return hhmm(now) === s.dailyAt;
  return now.getUTCDay() === s.weeklyAt.day && hhmm(now) === s.weeklyAt.time;
}

export async function tick(now: Date = new Date()): Promise<string[]> {
  const minute = now.toISOString().slice(0, 16);
  const ran: string[] = [];
  for (const job of jobs.values()) {
    if (!isDue(job.schedule, now)) continue;
    const prev = jobRuns.get(job.name);
    if (prev?.lastRunMinute === minute) continue;
    if (prev) jobRuns.update(job.name, { lastRunMinute: minute });
    else jobRuns.insert({ id: job.name, lastRunMinute: minute });
    try {
      await job.run(now);
      ran.push(job.name);
    } catch (err) {
      console.error(`job ${job.name} failed`, err);
    }
  }
  return ran;
}
