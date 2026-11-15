import sharp from "sharp";
import { getObject, putObject } from "./storage";

export const SIZES = [128, 512] as const;

/** Writes uploads/<id>/thumb-<size>.webp for each size. Overwrites, so it's safe to rerun. */
export async function makeThumbnails(uploadId: string, key: string): Promise<string[]> {
  const original = await getObject(key);
  const written: string[] = [];
  for (const size of SIZES) {
    const out = await sharp(original).resize(size, size, { fit: "inside" }).webp({ quality: 80 }).toBuffer();
    const thumbKey = `uploads/${uploadId}/thumb-${size}.webp`;
    await putObject(thumbKey, out, "image/webp");
    written.push(thumbKey);
  }
  return written;
}
