/**
 * Mirror of exploration/backend/planner.py::is_grounded_objective (contract 1.1.0).
 * The backend is authoritative (it returns 422); this only lets the composer explain the
 * rule before the request is sent.
 */
const DEICTIC = new Set(
  (
    "a an the is are was were be it this that these those true false correct right accurate real really actually valid " +
    "verify check confirm test prove challenge investigate look into please can could you we does do did what why how about " +
    "so just still claim claims fact facts source sources evidence more again further and or of for on in to if whether"
  ).split(" "),
);

export function contentWords(text: string): string[] {
  const words = text.toLowerCase().match(/[a-z0-9$%][a-z0-9$%.,'’-]*/g) ?? [];
  return words.map((w) => w.replace(/^[.,'’-]+|[.,'’-]+$/g, "")).filter((w) => w.length > 1 && !DEICTIC.has(w));
}

export function isGroundedObjective(objective: string): boolean {
  return contentWords(objective ?? "").length >= 2;
}
