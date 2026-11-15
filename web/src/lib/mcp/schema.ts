import type { StandardSchemaWithJSON } from "@modelcontextprotocol/server";

export type JsonSchema = Record<string, unknown>;

// The SDK wants a Standard Schema; ours is already JSON Schema and the API validates the values.
export function fromJsonSchema(schema: JsonSchema): StandardSchemaWithJSON {
  return {
    "~standard": {
      version: 1,
      vendor: "decision-flow",
      validate: (value: unknown) => ({ value }),
      jsonSchema: { input: () => schema, output: () => schema },
    },
  };
}
