import { describe, expect, it } from "vitest";
import { roleFromToken } from "./sessionRole";
import { fakeJwt } from "../test/utils";

describe("roleFromToken", () => {
  it("reads the admin workspace from the signed claim", () => {
    expect(roleFromToken(fakeJwt({ role: "admin" }))).toBe("admin");
  });

  it("reads the HR workspace", () => {
    expect(roleFromToken(fakeJwt({ role: "user" }))).toBe("user");
  });

  it("treats tokens without a role (issued before workspaces) as HR", () => {
    expect(roleFromToken(fakeJwt({}))).toBe("user");
  });

  it("never returns an unknown role", () => {
    expect(roleFromToken(fakeJwt({ role: "superadmin" }))).toBe("user");
    expect(roleFromToken(fakeJwt({ role: ["admin"] }))).toBe("user");
  });

  it("falls back to HR for malformed tokens", () => {
    expect(roleFromToken("")).toBe("user");
    expect(roleFromToken("not-a-jwt")).toBe("user");
    expect(roleFromToken("a.%%%.c")).toBe("user");
  });

  it("decodes base64url payloads (- and _ characters)", () => {
    // A long value makes '-'/'_' very likely to appear in the encoding.
    const token = fakeJwt({ role: "admin", note: "?>?>?>~~~~".repeat(20) });
    expect(roleFromToken(token)).toBe("admin");
  });
});
