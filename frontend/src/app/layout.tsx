import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Docs Studio", template: "%s · Docs Studio" },
  description: "Documentation, written and published with care.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
