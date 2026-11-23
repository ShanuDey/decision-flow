import { z } from "zod";

import { ACTIONS, type Action, hasAction, type Permissions } from "./scopes";

export const MAX_KEYS = 20;
export const NAME_MAX = 32;

export const EXPIRY_OPTIONS = [
  { value: "30", label: "30 days", days: 30 },
  { value: "90", label: "90 days", days: 90 },
  { value: "365", label: "1 year", days: 365 },
  { value: "never", label: "Never", days: null },
] as const;
export const DEFAULT_EXPIRY = "90";

export const createKeyBody = z.object({
  name: z.string().trim().min(1).max(NAME_MAX),
  actions: z.array(z.enum(ACTIONS)).min(1),
  expiresInDays: z.union([z.literal(30), z.literal(90), z.literal(365), z.null()]),
});
export type CreateKeyBody = z.infer<typeof createKeyBody>;

export function expiryDays(value: string): CreateKeyBody["expiresInDays"] {
  return EXPIRY_OPTIONS.find((option) => option.value === value)?.days ?? null;
}

export function expiresInSeconds(days: CreateKeyBody["expiresInDays"]): number | null {
  return days === null ? null : days * 24 * 60 * 60;
}

export function actionsOf(permissions: Permissions | null | undefined): Action[] {
  return ACTIONS.filter((action) => hasAction(permissions, action));
}

export function keyStatus(expiresAt: string | null, now: Date = new Date()): "active" | "expired" {
  return expiresAt !== null && new Date(expiresAt) <= now ? "expired" : "active";
}

export function formatKeyDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", { dateStyle: "medium", timeZone: "UTC" });
}
