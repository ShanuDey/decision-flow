import { describe, expect, it } from "vitest";

import { authErrorMessage, initials, methodLabel, providerLabel } from "./format";

describe("initials", () => {
  it("uses the first letters of the first and last name", () => {
    expect(initials("Alex Rivera", null)).toBe("AR");
    expect(initials("Mary Jane Watson", null)).toBe("MW");
  });

  it("uses two letters of a single name", () => {
    expect(initials("alex", null)).toBe("AL");
  });

  it("falls back to the email local part, then to a placeholder", () => {
    expect(initials("", "sam.lee@acme.com")).toBe("SL");
    expect(initials(null, "x@acme.com")).toBe("X");
    expect(initials(null, null)).toBe("?");
    expect(initials("  ", "")).toBe("?");
  });

  it("ignores emoji and punctuation", () => {
    expect(initials("🚀 Alex", null)).toBe("AL");
  });
});

describe("labels", () => {
  it("names the login methods", () => {
    expect(methodLabel("github")).toBe("GitHub");
    expect(methodLabel("password")).toBe("Email and password");
    expect(methodLabel("apple")).toBe("Apple");
  });

  it("maps Better Auth provider ids to a label", () => {
    expect(providerLabel("credential")).toBe("Email and password");
    expect(providerLabel("google")).toBe("Google");
    expect(providerLabel("okta")).toBe("Okta");
  });
});

describe("authErrorMessage", () => {
  it("shows nothing when there is no error", () => {
    expect(authErrorMessage(undefined)).toBeNull();
    expect(authErrorMessage("")).toBeNull();
  });

  it("explains the codes people actually hit", () => {
    expect(authErrorMessage("access_denied")).toBe("Sign-in was cancelled.");
    expect(authErrorMessage("account_not_linked")).toContain("already belongs to another account");
    expect(authErrorMessage("state_mismatch")).toContain("expired");
  });

  it("uses the first value of a repeated parameter", () => {
    expect(authErrorMessage(["access_denied", "x"])).toBe("Sign-in was cancelled.");
  });

  it("never echoes an unknown code back into the page", () => {
    const message = authErrorMessage("<script>alert(1)</script>");
    expect(message).toContain("Sign-in failed");
    expect(message).not.toContain("script");
  });
});

