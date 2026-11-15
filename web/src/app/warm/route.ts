import { wakeApi } from "@/lib/wake";

export const maxDuration = 60;

// Public: the sign-in page wakes the API through it. Answers first so no function stays open.
export function GET(): Response {
  wakeApi();
  return new Response(null, { status: 204 });
}
