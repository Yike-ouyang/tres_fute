import type { EngineAction } from "./client";
import type { GameState, PlayerId, PlayerScore } from "../game/types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

export interface ReplayManifestEntry {
  id: string;
  run: string;
  checkpoint: string;
  seed: number;
  agent_player: PlayerId;
  file: string;
  agent_decisions: number;
  frames: number;
  final_scores: { agent: number; adversary: number } | null;
  result: string | null;
}

export interface ReplayDice {
  color: string;
  value: number;
  location: "available" | "chosen" | "discarded";
  joker_value: number | null;
}

export interface ReplayObservationSummary {
  agent_player: PlayerId;
  scores: { agent: number; adversary: number };
  fox_count: { agent: number; adversary: number };
  turn: number;
  round: number;
  phase: string;
  decision: string;
  actor: "agent" | "adversary";
  active_is_agent: boolean;
  dice: ReplayDice[];
  selected_die: string | null;
  selection: {
    color: string | null;
    acting_color: string | null;
    value: number;
    max_pick: number;
    picked_cells: number;
    legal_cells: number;
  } | null;
  bonuses: {
    agent: Record<string, { unlocked: number; used: number }>;
    adversary: Record<string, { unlocked: number; used: number }>;
  };
  pending_bonuses: { owner: string; color: string }[];
  joker_pending: boolean;
}

export interface ReplayFrame {
  index: number;
  /** Who produced the atomic engine action. */
  role: "agent" | "opponent" | "auto";
  actor: PlayerId | null;
  decision_kind: string;
  action: EngineAction & { [key: string]: unknown };
  state: GameState;
  decision: { kind: string; actor: PlayerId | null; [key: string]: unknown };
  scores: Record<"1" | "2", PlayerScore>;
  message: string | null;
  /** Set on the first atomic action of an RL decision. */
  rl: { id: number; label: string } | null;
  /** Present on agent decision frames (summary of the numeric observation). */
  observation_summary?: ReplayObservationSummary;
  /** Legal RL actions at the agent decision (id + label). */
  legal_actions?: { id: number; label: string }[];
}

export interface ReplayTrace {
  run: string;
  checkpoint: string;
  seed: number;
  agent_player: PlayerId;
  rules_version: string | null;
  observation_version: string;
  action_version: string;
  n_actions: number;
  initial_state: GameState;
  frames: ReplayFrame[];
  final_scores: { agent: number; adversary: number } | null;
  result: string | null;
  agent_decisions: number;
  created: string;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || "Erreur réseau");
  }
  return (await res.json()) as T;
}

export async function listReplays(): Promise<ReplayManifestEntry[]> {
  const data = await getJson<{ replays: ReplayManifestEntry[] }>("/replays");
  return data.replays;
}

export async function getReplay(id: string): Promise<ReplayTrace> {
  return getJson<ReplayTrace>(`/replays/${encodeURIComponent(id)}`);
}
