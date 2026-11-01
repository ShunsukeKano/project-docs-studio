import Link from "next/link";

import { Brand } from "@/components/ui/brand";

const navLink =
  "rounded-md px-2.5 py-1.5 text-sm text-muted transition-colors hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-line/70 bg-surface/85 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <Brand href="/docs" />
          <nav className="flex items-center gap-1" aria-label="Main">
            <Link href="/docs" className={navLink}>
              Articles
            </Link>
            <Link href="/studio" className={navLink}>
              Writer area
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10">{children}</main>
      <footer className="border-t border-line/70 py-6 text-center text-xs text-faint">
        Docs Studio · every page shows the last published version
      </footer>
    </div>
  );
}
