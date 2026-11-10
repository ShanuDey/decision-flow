import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clampWidth,
  DEFAULT_WIDTH,
  loadStored,
  maxWidth,
  MIN_WIDTH,
  saveStored,
  useLayout,
} from "./layout";

describe("clampWidth", () => {
  it("keeps widths between the minimum and 60% of the viewport", () => {
    expect(clampWidth(100, 1600)).toBe(MIN_WIDTH);
    expect(clampWidth(500, 1600)).toBe(500);
    expect(clampWidth(5000, 1600)).toBe(960);
    expect(maxWidth(1600)).toBe(960);
  });

  it("never goes below the minimum, even in a tiny window", () => {
    expect(maxWidth(300)).toBe(MIN_WIDTH);
    expect(clampWidth(900, 300)).toBe(MIN_WIDTH);
  });

  it("rounds to whole pixels", () => {
    expect(clampWidth(412.6, 1600)).toBe(413);
  });
});

describe("stored layout", () => {
  const storage = (value: string | null) => ({ getItem: () => value });

  it("falls back to the defaults when nothing usable is stored", () => {
    const defaults = { width: DEFAULT_WIDTH, collapsed: false };
    expect(loadStored(storage(null))).toEqual(defaults);
    expect(loadStored(storage("not json"))).toEqual(defaults);
    expect(loadStored(undefined)).toEqual(defaults);
    expect(
      loadStored({
        getItem: () => {
          throw new Error("blocked");
        },
      }),
    ).toEqual(defaults);
  });

  it("reads a saved width and collapsed flag, ignoring bad fields", () => {
    expect(loadStored(storage('{"width": 480, "collapsed": true}'))).toEqual({
      width: 480,
      collapsed: true,
    });
    expect(loadStored(storage('{"width": "wide", "collapsed": "yes"}'))).toEqual({
      width: DEFAULT_WIDTH,
      collapsed: false,
    });
  });

  it("round-trips and survives a storage that throws on write", () => {
    let saved = "";
    saveStored({ width: 400, collapsed: true }, { setItem: (_k, v) => (saved = v) });
    expect(loadStored(storage(saved))).toEqual({ width: 400, collapsed: true });
    expect(() =>
      saveStored(
        { width: 400, collapsed: true },
        {
          setItem: () => {
            throw new Error("quota");
          },
        },
      ),
    ).not.toThrow();
  });
});

describe("layout store", () => {
  it("expand() opens a collapsed panel and does nothing when it is already open", () => {
    useLayout.setState({ collapsed: true });
    useLayout.getState().expand();
    expect(useLayout.getState().collapsed).toBe(false);
    useLayout.getState().expand();
    expect(useLayout.getState().collapsed).toBe(false);
  });

  it("toggleCollapsed() flips the state and reset() restores the default width", () => {
    useLayout.setState({ collapsed: false, width: 500 });
    useLayout.getState().toggleCollapsed();
    expect(useLayout.getState().collapsed).toBe(true);
    useLayout.getState().reset();
    expect(useLayout.getState().width).toBe(DEFAULT_WIDTH);
  });
});

describe("persistence while resizing", () => {
  afterEach(() => vi.unstubAllGlobals());

  function stubBrowser() {
    const setItem = vi.fn();
    vi.stubGlobal("window", {
      innerWidth: 1600,
      localStorage: { getItem: () => null, setItem },
    });
    useLayout.setState({ width: DEFAULT_WIDTH, collapsed: false });
    return setItem;
  }

  it("keeps drag updates in memory and writes once on persist()", () => {
    const setItem = stubBrowser();
    useLayout.getState().setWidth(400, { persist: false });
    useLayout.getState().setWidth(420, { persist: false });
    expect(useLayout.getState().width).toBe(420);
    expect(setItem).not.toHaveBeenCalled();

    useLayout.getState().persist();
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(JSON.parse(setItem.mock.calls[0][1])).toEqual({ width: 420, collapsed: false });
  });

  it("persists immediately for one-off changes like the keyboard", () => {
    const setItem = stubBrowser();
    useLayout.getState().setWidth(500);
    expect(setItem).toHaveBeenCalledTimes(1);
    expect(useLayout.getState().width).toBe(500);
  });

  it("clamps to the window while dragging", () => {
    stubBrowser();
    useLayout.getState().setWidth(5000, { persist: false });
    expect(useLayout.getState().width).toBe(960);
  });
});

describe("focus requests", () => {
  it("replaces the request object each time so repeats still fire", () => {
    useLayout.getState().requestFocus({ select: false });
    const first = useLayout.getState().focusRequest;
    useLayout.getState().requestFocus({ select: false });
    expect(useLayout.getState().focusRequest).not.toBe(first);
  });
});
