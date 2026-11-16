import type { Variable } from "./types";

export function nextVariableName(variables: Variable[]): string {
  const taken = new Set(variables.map((v) => v.name));
  let n = 1;
  while (taken.has(`var_${n}`)) n += 1;
  return `var_${n}`;
}
