import type { ReplayFrame } from "./api/replays";

/**
 * Positions run from 0 to ``frames.length``:
 *   - position 0 shows the initial state (before any action);
 *   - position p (1..N) shows the state after frame ``p - 1``.
 */
export function clampIndex(index: number, frameCount: number): number {
  if (Number.isNaN(index)) return 0;
  return Math.max(0, Math.min(frameCount, Math.trunc(index)));
}

export function frameAt(index: number, frames: ReplayFrame[]): ReplayFrame | null {
  if (index <= 0 || index > frames.length) return null;
  return frames[index - 1];
}

/** Next position whose frame begins an agent (RL) decision, else the last position. */
export function nextAgentIndex(index: number, frames: ReplayFrame[]): number {
  for (let p = clampIndex(index, frames.length) + 1; p <= frames.length; p += 1) {
    if (frames[p - 1].rl) return p;
  }
  return frames.length;
}

/** Previous position whose frame begins an agent (RL) decision, else the first position. */
export function prevAgentIndex(index: number, frames: ReplayFrame[]): number {
  for (let p = clampIndex(index, frames.length) - 1; p >= 1; p -= 1) {
    if (frames[p - 1].rl) return p;
  }
  return 0;
}
