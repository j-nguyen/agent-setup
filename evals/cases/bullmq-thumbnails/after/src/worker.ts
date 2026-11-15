import { Worker } from "bullmq";
import { THUMBNAIL_QUEUE, type ThumbnailJob } from "./queues";
import { redis } from "./redis";
import { makeThumbnails } from "./thumbnail";

const worker = new Worker<ThumbnailJob, string[]>(
  THUMBNAIL_QUEUE,
  async (job) => {
    const keys = await makeThumbnails(job.data.uploadId, job.data.key);
    await job.updateProgress(100);
    return keys;
  },
  { connection: redis, concurrency: 4 },
);

worker.on("failed", (job, err) => {
  console.error(`thumbnail job ${job?.id} for ${job?.data.uploadId} failed: ${err.message}`);
});

console.log("thumbnail worker started");
