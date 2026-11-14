import { describe, expect, it } from "vitest";

import {
  errorResponse,
  hasBody,
  isAllowedOrigin,
  isSafeMethod,
  publicLocation,
  responseHeaders,
  apiInit,
  clientIpHeaders,
  upstreamHeaders,
  upstreamPath,
} from "./backend-proxy";

const API = "http://api.internal:8000";

describe("upstreamPath", () => {
  it("joins and encodes segments", () => {
    expect(upstreamPath(["flows", "abc", "validate"])).toBe("/flows/abc/validate");
    expect(upstreamPath(["flows", "a b"])).toBe("/flows/a%20b");
  });

  it("rejects traversal, empty and separator segments", () => {
    for (const bad of [[], [".."], ["flows", ".."], ["."], [""], ["a/b"], ["a\\b"]]) {
      expect(upstreamPath(bad)).toBeNull();
    }
  });
});

describe("methods", () => {
  it("treats only GET, HEAD and OPTIONS as safe", () => {
    expect(["GET", "head", "OPTIONS"].every(isSafeMethod)).toBe(true);
    expect(["POST", "PUT", "PATCH", "DELETE"].some(isSafeMethod)).toBe(false);
  });

  it("sends a body for everything except GET and HEAD", () => {
    expect(hasBody("GET")).toBe(false);
    expect(hasBody("head")).toBe(false);
    expect(hasBody("POST")).toBe(true);
    expect(hasBody("DELETE")).toBe(true);
  });
});

describe("isAllowedOrigin", () => {
  const app = "https://demo.example.com";

  it("accepts only the app's own origin", () => {
    expect(isAllowedOrigin("https://demo.example.com", app)).toBe(true);
    expect(isAllowedOrigin("https://evil.example.com", app)).toBe(false);
    expect(isAllowedOrigin("http://demo.example.com", app)).toBe(false);
    expect(isAllowedOrigin("https://demo.example.com.evil.test", app)).toBe(false);
  });

  it("rejects a missing or malformed origin", () => {
    expect(isAllowedOrigin(null, app)).toBe(false);
    expect(isAllowedOrigin("not a url", app)).toBe(false);
  });
});

describe("upstreamHeaders", () => {
  it("forwards only allow-listed headers and sets the bearer token", () => {
    const incoming = new Headers({
      cookie: "better-auth.session_token=secret",
      authorization: "Bearer forged",
      "x-forwarded-for": "6.6.6.6",
      "x-auth-provider": "other",
      "content-type": "application/json",
      "if-match": "3",
    });
    const out = upstreamHeaders(incoming, "tok");
    expect(out.get("authorization")).toBe("Bearer tok");
    expect(out.get("content-type")).toBe("application/json");
    expect(out.get("if-match")).toBe("3");
    for (const name of ["cookie", "x-forwarded-for", "x-auth-provider"]) {
      expect(out.has(name)).toBe(false);
    }
  });
});

describe("visitor IP", () => {
  it("forwards the first entry of the configured header, never the browser's own x-client-ip", () => {
    const incoming = new Headers({ "x-forwarded-for": "5.5.5.5, 10.0.0.1", "x-client-ip": "6.6.6.6" });
    expect(upstreamHeaders(incoming, "tok").get("x-client-ip")).toBe("5.5.5.5");
    expect(upstreamHeaders(incoming, "tok", "x-other").has("x-client-ip")).toBe(false);
    expect(clientIpHeaders(new Headers(), "x-forwarded-for")).toEqual({});
  });
});

describe("apiInit", () => {
  it("sends the token and the visitor IP from the configured header", () => {
    const incoming = new Headers({ "x-forwarded-for": "5.5.5.5, 10.0.0.1", "x-client-ip": "6.6.6.6" });
    expect(apiInit("tok", incoming, "x-forwarded-for").headers).toEqual({
      Authorization: "Bearer tok",
      "x-client-ip": "5.5.5.5",
    });
  });

  it("omits the visitor IP when the platform header is missing", () => {
    const incoming = new Headers({ "x-client-ip": "6.6.6.6" });
    expect(apiInit("tok", incoming, "x-forwarded-for").headers).toEqual({
      Authorization: "Bearer tok",
    });
  });
});

describe("publicLocation", () => {
  it("maps a same-origin redirect under the public prefix", () => {
    expect(publicLocation(`${API}/flows?page=2`, API)).toBe("/backend/flows?page=2");
    expect(publicLocation("/flows/", API)).toBe("/backend/flows/");
  });

  it("drops redirects to other hosts and missing locations", () => {
    expect(publicLocation("https://elsewhere.test/x", API)).toBeNull();
    expect(publicLocation(null, API)).toBeNull();
  });
});

describe("responseHeaders", () => {
  it("strips hop-by-hop, cookie and server headers and keeps the rest", () => {
    const upstream = new Headers({
      "content-type": "application/json",
      "content-length": "12",
      "content-encoding": "gzip",
      "set-cookie": "x=1",
      server: "uvicorn",
      "www-authenticate": "Bearer",
      etag: '"v1"',
      location: `${API}/flows/`,
    });
    const out = responseHeaders(upstream, API);
    expect(out.get("content-type")).toBe("application/json");
    expect(out.get("etag")).toBe('"v1"');
    expect(out.get("location")).toBe("/backend/flows/");
    for (const name of ["content-length", "content-encoding", "set-cookie", "server"]) {
      expect(out.has(name)).toBe(false);
    }
    expect(out.has("www-authenticate")).toBe(false);
  });

  it("never exposes the backend address", () => {
    const out = responseHeaders(new Headers({ location: `${API}/a`, "x-other": "ok" }), API);
    expect([...out.values()].join(" ")).not.toContain("api.internal");
  });
});

describe("errorResponse", () => {
  it("uses the shared error shape", async () => {
    const response = errorResponse(401, "unauthenticated", "Sign in required");
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({
      code: "unauthenticated",
      message: "Sign in required",
      details: {},
    });
  });
});

describe("isAllowedOrigin with trusted origins", () => {
  const app = "https://demo.example.com";

  it("accepts an extra configured origin and nothing else", () => {
    const extra = ["https://preview.example.com"];
    expect(isAllowedOrigin("https://preview.example.com", app, extra)).toBe(true);
    expect(isAllowedOrigin("https://other.example.com", app, extra)).toBe(false);
  });
});
