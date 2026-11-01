export type ApiProblem = {
  status: number;
  code: string;
  message: string;
  /** Set for a `version_conflict`: the version the server holds now. */
  currentDraftVersion?: number;
};

/** Turn an error response into one plain shape. Never throws. */
export function toProblem(status: number, body: unknown): ApiProblem {
  const error = (body as { error?: { code?: unknown; message?: unknown; details?: unknown } })
    ?.error;
  const details = error?.details as { current_draft_version?: unknown } | null | undefined;
  return {
    status,
    code: typeof error?.code === "string" ? error.code : "unexpected_error",
    message:
      typeof error?.message === "string" ? error.message : "Something went wrong. Please retry.",
    currentDraftVersion:
      typeof details?.current_draft_version === "number" ? details.current_draft_version : undefined,
  };
}
