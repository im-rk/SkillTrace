/** The same forward update as backend/app/modules/quiz_engine/domain/bkt/engine.py, used only to
 * preview what a parameter choice does -- the server remains the single source of truth. */
export interface BktParams {
  p_l0: number;
  p_t: number;
  p_g: number;
  p_s: number;
}

export function updateMastery(prior: number, correct: boolean, { p_t, p_g, p_s }: BktParams): number {
  const numerator = correct ? prior * (1 - p_s) : prior * p_s;
  const denominator = numerator + (correct ? (1 - prior) * p_g : (1 - prior) * (1 - p_g));
  const posterior = denominator === 0 ? 0 : numerator / denominator;
  return Math.min(1, Math.max(0, posterior + (1 - posterior) * p_t));
}
