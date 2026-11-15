import { Queue } from "bullmq";
import { redis } from "./redis";

export interface ThumbnailJob {
  uploadId: string;
  key: string;
}

export const THUMBNAIL_QUEUE = "thumbnails";

export const thumbnailQueue = new Queue<ThumbnailJob>(THUMBNAIL_QUEUE, { connection: redis });
