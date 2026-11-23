import { beforeEach, describe, expect, it, vi } from "vitest";

const wakeApi = vi.hoisted(() => vi.fn());
vi.mock("./wake", () => ({ wakeApi }));
vi.mock("./auth/server", () => ({
  getConfig: () => ({ apiUrl: "http://api.test", ipHeader: "x-forwarded-for" }),
}));
vi.mock("./auth/session", () => ({ apiToken: async () => "signed-token" }));

import { forwardToApi } from "./gateway";

const fetchMock = vi.fn();
const user = { id: "user-1" };
const call = { method: "GET", path: "/flows", search: "?page=1", headers: new Headers() };

beforeEach(() => {
  fetchMock.mockReset();
  wakeApi.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("forwardToApi", () => {
  it("calls the API with the signed token and returns its answer", async () => {
    fetchMock.mockResolvedValue(new Response('{"items":[]}', { status: 200, headers: { "content-type": "application/json" } }));

    const response = await forwardToApi(call, user);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ items: [] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/flows?page=1");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer signed-token");
    expect(wakeApi).not.toHaveBeenCalled();
  });

  it("adds the headers we set and keeps them over anything the client sent", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));

    await forwardToApi(
      { ...call, headers: new Headers({ "x-df-source": "web" }) },
      user,
      { "x-df-source": "api", "x-external-user-id": "maria" },
    );

    const sent = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(sent.get("x-df-source")).toBe("api");
    expect(sent.get("x-external-user-id")).toBe("maria");
  });

  it("answers an empty 204 without a body", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const response = await forwardToApi({ ...call, method: "DELETE" }, user);
    expect(response.status).toBe(204);
    expect(await response.text()).toBe("");
  });

  it("answers 502 with a retry hint and wakes the API when it is unreachable", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));

    const response = await forwardToApi(call, user);

    expect(response.status).toBe(502);
    expect(response.headers.get("retry-after")).toBe("30");
    const body = await response.json();
    expect(body.code).toBe("upstream_unavailable");
    expect(body.message).toContain("Try again in about 30 seconds");
    expect(wakeApi).toHaveBeenCalledTimes(1);
  });

  it("passes the API's own error through untouched", async () => {
    fetchMock.mockResolvedValue(Response.json({ code: "not_found", message: "Flow not found", details: {} }, { status: 404 }));
    const response = await forwardToApi(call, user);
    expect(response.status).toBe(404);
    expect((await response.json()).code).toBe("not_found");
    expect(wakeApi).not.toHaveBeenCalled();
  });
});
