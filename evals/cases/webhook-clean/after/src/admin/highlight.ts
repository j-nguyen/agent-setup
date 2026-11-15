import { escapeHtml } from "./escape";

const REGEX_SPECIALS = /[.*+?^${}()|[\]\\]/g;

/**
 * HTML for `text` with every case-insensitive match of `term` wrapped in <mark>.
 * Both are escaped first, so the only markup in the result is the <mark> tags we add.
 */
export function highlight(text: string, term: string): string {
  const safeText = escapeHtml(text);
  if (!term) return safeText;
  const needle = escapeHtml(term).replace(REGEX_SPECIALS, "\\$&");
  return safeText.replace(new RegExp(needle, "gi"), (m) => `<mark>${m}</mark>`);
}
