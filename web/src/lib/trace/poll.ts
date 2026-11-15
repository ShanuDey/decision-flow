// Wait before rechecking a trace still being written: 1 s, backing off to 5 s.
const FIRST_MS = 1000;
const CEILING_MS = 5000;

export function pollDelay(poll: number): number {
  return Math.min(Math.round(FIRST_MS * 1.5 ** poll), CEILING_MS);
}
