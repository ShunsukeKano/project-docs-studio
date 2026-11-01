import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-24 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-muted">This page does not exist or is not available.</p>
      <p className="mt-6">
        <Link href="/docs" className="text-accent underline underline-offset-2">
          Back to the documentation
        </Link>
      </p>
    </main>
  );
}
