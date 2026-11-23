import { beforeEach, describe, expect, it, vi } from "vitest";

const forwardToApi = vi.hoisted(() => vi.fn());
vi.mock("./gateway", () => ({ forwardToApi }));
vi.mock("./auth/server", () => ({ getAuth: vi.fn(), getRuntime: vi.fn() }));

import type { Action } from "./auth/scopes";
import { callGateway, type GatewayCall } from "./gateway-v1";

const user = { id: "user-1", email: "a@acme.com" };
const auth = (...actions: Action[]) => ({ ok: true as const, user, actions });

const call = (method: string, path: string, extra: Partial<GatewayCall> = {}): GatewayCall => ({
  method,
  path,
  headers: new Headers({ "content-type": "application/json" }),
  ...extra,
});

beforeEach(() => {
  forwardToApi.mockReset();
  forwardToApi.mockImplementation(async () => new Response('{"items":[]}', { status: 200 }));
});

describe("callGateway", () => {
  it("answers 404 for a route outside the allowlist without calling the API", async () => {
    const response = await callGateway(call("GET", "/me"), auth("flows:read", "flows:write", "flows:run"));
    expect(response.status).toBe(404);
    expect(forwardToApi).not.toHaveBeenCalled();
  });

  it("answers 403 for a missing scope without calling the API", async () => {
    const response = await callGateway(call("POST", "/flows"), auth("flows:read"));
    expect(response.status).toBe(403);
    expect((await response.json()).code).toBe("insufficient_scope");
    expect(forwardToApi).not.toHaveBeenCalled();
  });

  it("forwards an allowed call as the key's owner and never caches it", async () => {
    const response = await callGateway(call("GET", "/flows", { search: "?page=2" }), auth("flows:read"));

    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(forwardToApi).toHaveBeenCalledTimes(1);
    const [forwarded, who] = forwardToApi.mock.calls[0];
    expect(forwarded).toMatchObject({ method: "GET", path: "/flows", search: "?page=2" });
    expect(who).toBe(user);
  });

  it("passes the body and headers of a normal write through", async () => {
    await callGateway(
      call("PUT", "/flows/abc/draft", { body: '{"nodes":[]}', headers: new Headers({ "if-match": "3" }) }),
      auth("flows:write"),
    );
    const [forwarded] = forwardToApi.mock.calls[0];
    expect(forwarded.body).toBe('{"nodes":[]}');
    expect(forwarded.headers.get("if-match")).toBe("3");
  });

  describe("agents", () => {
    const invoke = () => call("POST", "/agents/a1/invoke", { body: "{}" });

    it("refuses every agent route to a key that only has flow scopes", async () => {
      const flows = auth("flows:read", "flows:write", "flows:run");
      for (const [method, path] of [
        ["GET", "/agents"],
        ["GET", "/agents/a1/threads"],
        ["POST", "/agents/a1/threads"],
        ["POST", "/agents/a1/invoke"],
        ["POST", "/agents"],
      ]) {
        expect((await callGateway(call(method, path), flows)).status, `${method} ${path}`).toBe(403);
      }
      expect(forwardToApi).not.toHaveBeenCalled();
    });

    it("lets a chat key talk to an agent but not change it", async () => {
      const chat = auth("agents:chat");
      expect((await callGateway(invoke(), chat)).status).toBe(200);
      expect((await callGateway(call("POST", "/agents/a1/threads"), chat)).status).toBe(200);
      expect((await callGateway(call("PATCH", "/agents/a1"), chat)).status).toBe(403);
      expect((await callGateway(call("DELETE", "/agents/a1"), chat)).status).toBe(403);
      expect((await callGateway(call("GET", "/agents/a1/threads"), chat)).status).toBe(403);
    });

    it("keeps flow access out of a key that only has agent scopes", async () => {
      expect((await callGateway(call("GET", "/flows"), auth("agents:read", "agents:chat"))).status).toBe(403);
    });

    it("forwards an agent call as the key's owner with its body untouched", async () => {
      await callGateway(call("POST", "/agents/a1/invoke", { body: '{"threadId":"t"}' }), auth("agents:chat"));
      const [forwarded, who] = forwardToApi.mock.calls[0];
      expect(forwarded).toMatchObject({ method: "POST", path: "/agents/a1/invoke", body: '{"threadId":"t"}' });
      expect(who).toBe(user);
    });
  });

  describe("trigger", () => {
    it("runs the published version through the run route", async () => {
      await callGateway(
        call("POST", "/flows/abc/trigger", { body: '{"input":{"amount":5}}', headers: new Headers() }),
        auth("flows:run"),
      );
      const [forwarded] = forwardToApi.mock.calls[0];
      expect(forwarded.path).toBe("/flows/abc/runs");
      expect(JSON.parse(forwarded.body)).toEqual({ input: { amount: 5 }, test: false });
      expect(forwarded.headers.get("content-type")).toBe("application/json");
    });

    it("reads a streamed body too", async () => {
      const stream = new Response('{"input":{"amount":1}}').body;
      await callGateway(call("POST", "/flows/abc/trigger", { body: stream }), auth("flows:run"));
      expect(JSON.parse(forwardToApi.mock.calls[0][0].body)).toEqual({ input: { amount: 1 }, test: false });
    });

    it("treats a missing body as no input", async () => {
      await callGateway(call("POST", "/flows/abc/trigger"), auth("flows:run"));
      expect(JSON.parse(forwardToApi.mock.calls[0][0].body)).toEqual({ input: {}, test: false });
    });

    it("refuses a test flag with 422 and does not call the API", async () => {
      const response = await callGateway(
        call("POST", "/flows/abc/trigger", { body: '{"input":{},"test":true}' }),
        auth("flows:run"),
      );
      expect(response.status).toBe(422);
      expect(forwardToApi).not.toHaveBeenCalled();
    });

    it("needs the run scope", async () => {
      const response = await callGateway(call("POST", "/flows/abc/trigger", { body: "{}" }), auth("flows:read", "flows:write"));
      expect(response.status).toBe(403);
    });
  });
});
