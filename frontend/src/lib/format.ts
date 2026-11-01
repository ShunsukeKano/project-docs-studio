// Dates are shown in UTC so the server render and the browser render always agree.
const date = new Intl.DateTimeFormat("en-CA", { dateStyle: "medium", timeZone: "UTC" });
const dateTime = new Intl.DateTimeFormat("en-CA", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

export const formatDate = (value: string): string => date.format(new Date(value));
export const formatDateTime = (value: string): string => `${dateTime.format(new Date(value))} UTC`;

/** Turn a title into a slug suggestion: lowercase words joined by single hyphens. */
export function slugify(title: string): string {
  return title
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100)
    .replace(/-+$/g, "");
}

/** The slug to create with: the typed one, else one made from the title, else a generated name. */
export function slugForNewArticle(title: string, typed: string, randomPart: () => string): string {
  const chosen = stripAddress(typed);
  if (chosen) return chosen;
  return slugify(title) || `article-${randomPart()}`;
}

/** Keep only the slug if a whole address was typed or pasted ("/docs/my-slug" becomes "my-slug"). */
export function stripAddress(value: string): string {
  return value.trim().replace(/^https?:\/\/[^/]+/i, "").replace(/^\/+/, "").replace(/^docs\//i, "");
}

/** Split a comma-separated tag field the same way the API normalizes tags. */
export function parseTags(text: string): string[] {
  const seen = new Set<string>();
  for (const part of text.split(",")) {
    const tag = part.trim().toLowerCase();
    if (tag) seen.add(tag);
  }
  return [...seen];
}
