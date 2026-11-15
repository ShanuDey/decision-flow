const TRIGGER = /^\/flows\/([^/]+)\/trigger$/;

export function triggerTarget(path: string): string | null {
  const id = TRIGGER.exec(path)?.[1];
  return id ? `/flows/${id}/runs` : null;
}

export type TriggerBody = { ok: true; body: string } | { ok: false; message: string };

const SHAPE = 'Send a JSON object like {"input": {...}}';

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

// Never forwards `test`, so a trigger cannot run a draft.
export function triggerBody(text: string): TriggerBody {
  let parsed: unknown = {};
  if (text.trim() !== "") {
    try {
      parsed = JSON.parse(text);
    } catch {
      return { ok: false, message: `The body is not valid JSON. ${SHAPE}` };
    }
  }
  if (!isObject(parsed)) return { ok: false, message: SHAPE };
  const extra = Object.keys(parsed).filter((key) => key !== "input");
  if (extra.length > 0) {
    return { ok: false, message: `Unknown field ${JSON.stringify(extra[0])}. ${SHAPE}` };
  }
  const input = "input" in parsed ? parsed.input : {};
  if (!isObject(input)) return { ok: false, message: `"input" must be a JSON object. ${SHAPE}` };
  return { ok: true, body: JSON.stringify({ input, test: false }) };
}
