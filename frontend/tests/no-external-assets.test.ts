import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = join(__dirname, "..");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "generated" ? [] : sourceFiles(path);
    return /\.(ts|tsx|css)$/.test(name) ? [path] : [];
  });
}

const files = sourceFiles(join(root, "src"));
const text = (path: string) => readFileSync(path, "utf8");

describe("images stay inside the app", () => {
  it("never names an image host or an absolute image address in the source", () => {
    const offenders = files.filter((file) =>
      /unsplash\.com|images\.[a-z]+\.[a-z]+|\bsrc=["'{`]*https?:|url\(\s*["']?https?:/i.test(text(file)),
    );
    expect(offenders).toEqual([]);
  });

  it("does not configure remote image hosts", () => {
    expect(text(join(root, "next.config.ts"))).not.toMatch(/remotePatterns|domains\s*:/);
  });

  it("only references local images, and every one of them exists in public/", () => {
    const referenced = files.flatMap((file) => [...text(file).matchAll(/["'`](\/images\/[^"'`]+)["'`]/g)].map((m) => m[1]!));
    expect(referenced.length).toBeGreaterThan(0);
    for (const path of referenced) {
      expect(existsSync(join(root, "public", path)), path).toBe(true);
    }
  });
});
