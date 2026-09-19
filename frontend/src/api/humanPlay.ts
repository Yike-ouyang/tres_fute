import type { ActingColor, GameState, PlayerId, PlayerScore } from "../game/types";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

export interface HumanLegalAction {
  id: number;
  label: string;
  detail: string;
  category: string;
  factorised_step1: boolean;
}

export interface HumanLastAi {
  kind: "move" | "factorised-step1";
  id?: number;
  label?: string;
  actions?: unknown[];
}

export interface HumanPlayState {
  session_id: string | null;
  seed: number;
  rules_version: string;
  human_player: PlayerId;
  opponent: "human" | "ai";
  checkpoint: string | null;
  opponent_name?: string | null;
  opponent_relpath?: string | null;
  is_over: boolean;
  human_turn: boolean;
  acting_player: PlayerId | null;
  awaiting_value: boolean;
  human_decisions: number;
  last_ai_actions: HumanLastAi[];
  legal_actions: HumanLegalAction[];
  final_scores: { agent: number; adversary: number } | null;
  state: GameState;
  scores: Record<"1" | "2", PlayerScore>;
  decision: { kind: string; actor: PlayerId | null; [key: string]: unknown };
  whiteAvailability: Record<ActingColor, boolean> | null;
}

export interface CreateHumanSessionBody {
  agent_player?: PlayerId;
  opponent?: "human" | "ai";
  checkpoint?: string | null;
  seed?: number | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
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

export async function createHumanSession(
  body: CreateHumanSessionBody
): Promise<{ session_id: string; state: HumanPlayState }> {
  return request("/human_play/sessions", { method: "POST", body: JSON.stringify(body) });
}

export async function getHumanSession(sessionId: string): Promise<HumanPlayState> {
  return request(`/human_play/sessions/${encodeURIComponent(sessionId)}`);
}

export async function getHumanLegalActions(sessionId: string): Promise<HumanLegalAction[]> {
  const data = await request<{ actions: HumanLegalAction[] }>(
    `/human_play/sessions/${encodeURIComponent(sessionId)}/legal_actions`
  );
  return data.actions;
}

export async function stepHumanSession(sessionId: string, actionId: number): Promise<HumanPlayState> {
  return request(`/human_play/sessions/${encodeURIComponent(sessionId)}/step`, {
    method: "POST",
    body: JSON.stringify({ action_id: actionId }),
  });
}

export async function cancelHumanSession(sessionId: string): Promise<HumanPlayState> {
  return request(`/human_play/sessions/${encodeURIComponent(sessionId)}/step`, {
    method: "POST",
    body: JSON.stringify({ cancel: true }),
  });
}

export interface HumanModelEntry {
  path: string;
  relpath: string;
  run: string;
  subdir: string;
  file: string;
  mtime: number;
  catalogue: "v1" | "v2";
  is_default: boolean;
}

export async function listHumanModels(): Promise<HumanModelEntry[]> {
  const data = await request<{ models: HumanModelEntry[] }>("/human_play/models");
  return data.models;
}

export async function deleteHumanSession(sessionId: string): Promise<void> {
  await request(`/human_play/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
}

export async function saveHumanSession(
  sessionId: string,
  path?: string
): Promise<{ replay_id: string; file: string }> {
  return request(`/human_play/sessions/${encodeURIComponent(sessionId)}/save`, {
    method: "POST",
    body: JSON.stringify({ path: path ?? null }),
  });
}
