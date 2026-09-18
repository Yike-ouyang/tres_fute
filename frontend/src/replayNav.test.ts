import { describe, expect, it } from "vitest";
import type { ReplayFrame } from "./api/replays";
import { clampIndex, frameAt, nextAgentIndex, prevAgentIndex } from "./replayNav";

function frame(index: number, isAgentDecision: boolean): ReplayFrame {
  return { index, rl: isAgentDecision ? { id: 0, label: "x" } : null } as unknown as ReplayFrame;
}

// positions: 0 initial; frames f0(auto) f1(agent) f2(agent) f3(auto) f4(agent)
const frames = [frame(0, false), frame(1, true), frame(2, true), frame(3, false), frame(4, true)];

describe("replayNav", () => {
  it("clamps to [0, frameCount]", () => {
    expect(clampIndex(-3, 5)).toBe(0);
    expect(clampIndex(0, 5)).toBe(0);
    expect(clampIndex(5, 5)).toBe(5);
    expect(clampIndex(99, 5)).toBe(5);
    expect(clampIndex(Number.NaN, 5)).toBe(0);
  });

  it("maps positions to frames (0 is the initial state)", () => {
    expect(frameAt(0, frames)).toBeNull();
    expect(frameAt(1, frames)?.index).toBe(0);
    expect(frameAt(5, frames)?.index).toBe(4);
    expect(frameAt(6, frames)).toBeNull();
  });

  it("jumps to the next agent decision", () => {
    expect(nextAgentIndex(0, frames)).toBe(2);
    expect(nextAgentIndex(2, frames)).toBe(3);
    expect(nextAgentIndex(3, frames)).toBe(5);
    expect(nextAgentIndex(5, frames)).toBe(5);
  });

  it("jumps to the previous agent decision", () => {
    expect(prevAgentIndex(5, frames)).toBe(3);
    expect(prevAgentIndex(3, frames)).toBe(2);
    expect(prevAgentIndex(2, frames)).toBe(0);
    expect(prevAgentIndex(1, frames)).toBe(0);
  });
});
