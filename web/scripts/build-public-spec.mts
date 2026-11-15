import { readFileSync, writeFileSync } from "node:fs";

import { buildPublicSpec, type OpenApiDoc } from "../src/lib/docs/public-spec.ts";

const source = new URL("../../api/openapi.json", import.meta.url);
const target = new URL("../src/lib/docs/public-openapi.json", import.meta.url);

const full = JSON.parse(readFileSync(source, "utf8")) as OpenApiDoc;
writeFileSync(target, `${JSON.stringify(buildPublicSpec(full), null, 2)}\n`);
