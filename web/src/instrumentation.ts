export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;
  const { bootstrapAuth } = await import("@/lib/auth/bootstrap");
  await bootstrapAuth();
}
