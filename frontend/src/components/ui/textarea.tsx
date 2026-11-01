import type { TextareaHTMLAttributes } from "react";

import { fieldClasses } from "./input";

export function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${fieldClasses} font-mono leading-6 ${className}`.trim()} {...props} />;
}
