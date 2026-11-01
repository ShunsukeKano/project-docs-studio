import { createElement, type ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";

const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

/** Keep a link only if it is a web, secure web or mail address. Anything else is removed. */
function urlTransform(url: string): string {
  try {
    return ALLOWED_PROTOCOLS.has(new URL(url).protocol) ? url : "";
  } catch {
    return "";
  }
}

const sanitizeSchema = {
  ...defaultSchema,
  protocols: { ...defaultSchema.protocols, href: ["http", "https", "mailto"] },
};

/**
 * The one Markdown renderer, used by the public page and by the writer's preview.
 * Raw HTML is never rendered (it shows as text), images are dropped, and links are limited
 * to http, https and mailto.
 */
export function renderMarkdown(source: string): ReactElement {
  return createElement(
    ReactMarkdown,
    {
      urlTransform,
      rehypePlugins: [[rehypeSanitize, sanitizeSchema]],
      disallowedElements: ["img"],
      unwrapDisallowed: true,
      components: {
        a: ({ href, children }) =>
          createElement("a", { href, rel: "noopener noreferrer" }, children),
      },
    },
    source,
  );
}
