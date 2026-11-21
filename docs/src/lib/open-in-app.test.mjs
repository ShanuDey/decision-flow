import assert from "node:assert/strict";
import { test } from "node:test";

import { normalizeAppUrl, resolve, targetPath } from "./open-in-app.mjs";

test("accepts http and https, reduced to the origin", () => {
  assert.equal(normalizeAppUrl("https://flows.example.com"), "https://flows.example.com");
  assert.equal(normalizeAppUrl("  https://flows.example.com:8443/x/y?z=1#h  "), "https://flows.example.com:8443");
  assert.equal(normalizeAppUrl("http://localhost:3000/"), "http://localhost:3000");
  assert.equal(normalizeAppUrl("http://127.0.0.1:3000"), "http://127.0.0.1:3000");
  assert.equal(normalizeAppUrl("http://192.168.1.20:3000"), "http://192.168.1.20:3000");
  assert.equal(normalizeAppUrl("http://homeserver:3000/app"), "http://homeserver:3000");
});

test("refuses anything else", () => {
  for (const bad of [
    "javascript:alert(1)",
    "data:text/html,x",
    "ftp://example.com",
    "file:///etc/passwd",
    "https://user:pass@example.com",
    "//example.com",
    "example.com",
    "",
    null,
    undefined,
  ]) {
    assert.equal(normalizeAppUrl(bad), null, String(bad));
  }
});

test("targets come from a fixed list and unknown names fall back to home", () => {
  assert.equal(targetPath("marketplace"), "/marketplace");
  assert.equal(targetPath("connections"), "/connections");
  for (const name of ["nope", "", "__proto__", "constructor", "//evil.test", undefined]) {
    assert.equal(targetPath(name), "/", String(name));
  }
});

test("goes to the saved app, or asks when there is none or it is not usable", () => {
  assert.deepEqual(resolve("marketplace", "https://flows.example.com"), {
    kind: "go",
    url: "https://flows.example.com/marketplace",
  });
  assert.deepEqual(resolve("nope", "https://flows.example.com"), { kind: "go", url: "https://flows.example.com/" });
  assert.deepEqual(resolve("marketplace", null), { kind: "ask" });
  assert.deepEqual(resolve("marketplace", "javascript:alert(1)"), { kind: "ask" });
});
