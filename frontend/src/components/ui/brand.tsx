import Link from "next/link";

/** The logo: an accent square with a page glyph, and the site name. */
export function Brand({ href, suffix }: { href: string; suffix?: string }) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-2.5 rounded-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-accent"
    >
      <span
        aria-hidden
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-white shadow-sm transition-transform group-hover:-rotate-3"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M7 3h7l5 5v13H7z" />
          <path d="M14 3v5h5" />
          <path d="M10 13h6M10 17h6" />
        </svg>
      </span>
      <span className="text-base font-semibold tracking-tight text-ink">
        Docs Studio
        {suffix ? <span className="ml-1.5 font-normal text-muted">{suffix}</span> : null}
      </span>
    </Link>
  );
}
