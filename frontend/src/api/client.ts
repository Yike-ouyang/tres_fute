import type {
  ActingColor,
  DieColor,
  GameState,
  PlayerId,
  PlayerScore,
} from "../game/types";

export type EngineAction = {
  type: string;
  color?: DieColor | ActingColor;
  acting_color?: ActingColor;
  cell_id?: string;
  value?: number;
  option?: "points" | "bonus";
  token_index?: number;
};

export interface AdvanceStatus {
  running: boolean;
  completed: number;
  quota: number;
  message: string | null;
}

export interface GameSnapshot {
  id: string;
  version: number;
  rulesVersion: string;
  seed: number;
  events: unknown[];
  remainingTurns: number;
  advance: AdvanceStatus;
  state: GameState;
  legalActions: EngineAction[];
  scores: Record<"1" | "2", PlayerScore>;
  decision: { kind: string; actor: PlayerId | null; [k: string]: unknown };
  stuck: boolean;
  whiteAvailability: Record<ActingColor, boolean> | null;
  passiveFlags: { discardedHasMove: boolean; chosenFallback: boolean };
  actingColors: ActingColor[];
  error?: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public snapshot: GameSnapshot | null,
    message: string
  ) {
    super(message);
  }
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

async function parse(res: Response): Promise<GameSnapshot> {
  const data = (await res.json()) as GameSnapshot & { detail?: unknown };
  if (res.status === 409) {
    throw new ApiError(409, data, data.error ?? "Conflit de version");
  }
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : res.statusText;
    throw new ApiError(res.status, null, detail || "Erreur réseau");
  }
  return data;
}

export async function createGame(seed?: number): Promise<GameSnapshot> {
  const res = await fetch(`${BASE}/games`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(seed === undefined ? {} : { seed }),
  });
  return parse(res);
}

export async function getGame(id: string): Promise<GameSnapshot> {
  const res = await fetch(`${BASE}/games/${id}`);
  return parse(res);
}

export async function postAction(
  id: string,
  expectedVersion: number,
  action: EngineAction
): Promise<GameSnapshot> {
  const res = await fetch(`${BASE}/games/${id}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command_id: crypto.randomUUID(),
      expected_version: expectedVersion,
      action,
    }),
  });
  return parse(res);
}

export async function resetGame(
  id: string,
  expectedVersion: number,
  seed?: number
): Promise<GameSnapshot> {
  const res = await fetch(`${BASE}/games/${id}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command_id: crypto.randomUUID(),
      expected_version: expectedVersion,
      seed,
    }),
  });
  return parse(res);
}

export async function postAdvance(
  id: string,
  expectedVersion: number,
  n: number
): Promise<GameSnapshot> {
  const res = await fetch(`${BASE}/games/${id}/advance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command_id: crypto.randomUUID(),
      expected_version: expectedVersion,
      n,
    }),
  });
  return parse(res);
}
