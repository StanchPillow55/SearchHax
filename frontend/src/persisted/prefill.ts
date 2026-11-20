/**
 * Hand-off from the Knowledge view to the New Investigation form (this tab only).
 *
 * Carries the frontier question and, when the source investigation has a stored research
 * profile, which investigation to copy it from. The profile itself is never carried: the
 * backend reads it from the stored record (profile_from_investigation_id).
 */
export interface NewQuestionPrefill {
  question: string;
  profileFrom: { investigationId: string; profileId: string } | null;
}

export function encodePrefill(p: NewQuestionPrefill): string {
  return JSON.stringify({ v: 1, question: p.question, profileFrom: p.profileFrom });
}

/** Older builds stored the bare question string; that still reads as a question without a profile. */
export function decodePrefill(raw: string | null): NewQuestionPrefill {
  if (!raw) return { question: "", profileFrom: null };
  try {
    const v = JSON.parse(raw) as unknown;
    if (v && typeof v === "object" && (v as { v?: unknown }).v === 1) {
      const o = v as { question?: unknown; profileFrom?: unknown };
      const pf = o.profileFrom as { investigationId?: unknown; profileId?: unknown } | null | undefined;
      const profileFrom =
        pf && typeof pf.investigationId === "string" && pf.investigationId && typeof pf.profileId === "string" && pf.profileId
          ? { investigationId: pf.investigationId, profileId: pf.profileId }
          : null;
      return { question: typeof o.question === "string" ? o.question : "", profileFrom };
    }
  } catch {
    /* not JSON: a legacy bare question */
  }
  return { question: raw, profileFrom: null };
}
