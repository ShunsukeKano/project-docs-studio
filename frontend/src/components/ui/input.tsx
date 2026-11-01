import type { InputHTMLAttributes } from "react";

export const fieldClasses =
  "w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-faint " +
  "focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-accent";

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${fieldClasses} ${className}`.trim()} {...props} />;
}

export function Label({
  htmlFor,
  children,
  hint,
}: {
  htmlFor: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="mb-1 flex items-baseline justify-between text-sm font-medium text-ink">
      <span>{children}</span>
      {hint ? <span className="text-xs font-normal text-faint">{hint}</span> : null}
    </label>
  );
}
