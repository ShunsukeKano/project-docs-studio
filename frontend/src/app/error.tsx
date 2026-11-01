"use client";

import { Button } from "@/components/ui/button";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto max-w-2xl px-4 py-24 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="mt-2 text-sm text-muted">
        The page could not be loaded. Please try again in a moment.
      </p>
      <div className="mt-6">
        <Button variant="primary" onClick={reset}>
          Try again
        </Button>
      </div>
    </main>
  );
}
