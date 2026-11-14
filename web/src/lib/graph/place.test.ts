import { describe, expect, it } from "vitest";

import { freeSpot, NODE_BOX } from "./nodes";

const center = { x: 1000, y: 500 };
const centered = { x: 1000 - NODE_BOX.width / 2, y: 500 - NODE_BOX.height / 2 };

describe("freeSpot", () => {
  it("centers the node on the point when nothing is in the way", () => {
    expect(freeSpot(center, [])).toEqual(centered);
    expect(freeSpot(center, [{ x: 0, y: 0 }])).toEqual(centered);
  });

  it("nudges down-right until the spot is free", () => {
    const spot = freeSpot(center, [centered]);
    expect(spot.x).toBeGreaterThan(centered.x);
    expect(spot.y).toBeGreaterThan(centered.y);
    expect(spot.x - centered.x).toBe(spot.y - centered.y);
    const stillOverlaps =
      Math.abs(spot.x - centered.x) < NODE_BOX.width && Math.abs(spot.y - centered.y) < NODE_BOX.height;
    expect(stillOverlaps).toBe(false);
  });

  it("never stacks repeated adds at the same point", () => {
    const taken: { x: number; y: number }[] = [];
    for (let i = 0; i < 5; i++) taken.push(freeSpot(center, taken));
    const keys = new Set(taken.map((p) => `${p.x},${p.y}`));
    expect(keys.size).toBe(5);
  });

  it("terminates even when the area is crowded", () => {
    const crowd = Array.from({ length: 400 }, (_, i) => ({ x: centered.x + (i % 20) * 16, y: centered.y + Math.floor(i / 20) * 16 }));
    const spot = freeSpot(center, crowd);
    expect(Number.isFinite(spot.x) && Number.isFinite(spot.y)).toBe(true);
  });
});
