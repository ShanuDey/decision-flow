import { exportPKCS8, generateKeyPair, jwtVerify } from "jose";
import { beforeAll, describe, expect, it } from "vitest";

import { signApiToken, TOKEN_LIFETIME_SECONDS, type TokenConfig } from "./api-token";

let config: TokenConfig;
let publicKey: CryptoKey;

beforeAll(async () => {
  const pair = await generateKeyPair("RS256", { extractable: true });
  publicKey = pair.publicKey as CryptoKey;
  config = {
    signingKey: await exportPKCS8(pair.privateKey),
    issuer: "http://localhost:3000",
    audience: "decision-flow-api",
  };
});

describe("signApiToken", () => {
  it("signs a token the API can verify with the public key", async () => {
    const token = await signApiToken(
      { id: "u1", email: "a@acme.com", emailVerified: true, name: "Alex" },
      config,
    );
    const { payload, protectedHeader } = await jwtVerify(token, publicKey, {
      issuer: config.issuer,
      audience: config.audience,
    });
    expect(protectedHeader.alg).toBe("RS256");
    expect(payload).toMatchObject({
      sub: "u1",
      email: "a@acme.com",
      email_verified: true,
      name: "Alex",
    });
  });

  it("expires after five minutes", async () => {
    const token = await signApiToken({ id: "u1" }, config);
    const { payload } = await jwtVerify(token, publicKey);
    expect(payload.exp! - payload.iat!).toBe(TOKEN_LIFETIME_SECONDS);
    expect(TOKEN_LIFETIME_SECONDS).toBe(300);
  });

  it("never claims a verified email the provider did not verify", async () => {
    for (const emailVerified of [false, null, undefined]) {
      const token = await signApiToken({ id: "u1", email: "a@acme.com", emailVerified }, config);
      const { payload } = await jwtVerify(token, publicKey);
      expect(payload.email_verified).toBe(false);
    }
  });

  it("omits email and name claims when the user has none", async () => {
    const token = await signApiToken({ id: "u1" }, config);
    const { payload } = await jwtVerify(token, publicKey);
    expect(payload).not.toHaveProperty("email");
    expect(payload).not.toHaveProperty("name");
  });

  it("is rejected for another audience or issuer", async () => {
    const token = await signApiToken({ id: "u1" }, config);
    await expect(jwtVerify(token, publicKey, { audience: "someone-else" })).rejects.toThrow();
    await expect(jwtVerify(token, publicKey, { issuer: "https://evil.test" })).rejects.toThrow();
  });
});
