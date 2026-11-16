"use client";

import { Plus, Trash2 } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { nextVariableName } from "@/lib/graph/variables";
import { cn } from "@/lib/utils";

import {
  EnumValues,
  FieldError,
  Labeled,
  patch,
  TypedValueInput,
  typeChange,
  TypeSelect,
} from "./fields";
import { variableIssues } from "./issues";
import { useEditor } from "./store";

export function VariablesDialog() {
  const open = useEditor((s) => s.variablesOpen);
  const setOpen = useEditor((s) => s.setVariablesOpen);
  const variables = useEditor((s) => s.variables);
  const setVariables = useEditor((s) => s.setVariables);
  const selected = useEditor((s) => s.variablesSelected);
  const select = useEditor((s) => s.selectVariable);
  const allIssues = useEditor((s) => s.issues);
  const issues = variableIssues(allIssues);
  const focusName = useRef(false);

  const index = Math.min(selected, variables.length - 1);
  const current = variables[index];

  useEffect(() => {
    if (!focusName.current) return;
    focusName.current = false;
    const input = document.getElementById("var-name") as HTMLInputElement | null;
    input?.focus();
    input?.select();
  }, [index, variables.length]);

  function add() {
    setVariables([...variables, { name: nextVariableName(variables), type: "string" }]);
    select(variables.length);
    focusName.current = true;
  }

  function remove() {
    setVariables(variables.filter((_, j) => j !== index));
    select(Math.max(0, index - 1));
  }

  // The validator names the variable in quotes, so a row can be flagged without extra plumbing.
  const hasIssue = (name: string) => issues.some((i) => i.message.includes(`'${name}'`));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="flex h-[min(34rem,85vh)] flex-col sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Flow variables</DialogTitle>
          <DialogDescription>
            Declare the variables here. Assign nodes write to them and any value can read them as{" "}
            <code>{"{{ vars.name }}"}</code>.
          </DialogDescription>
        </DialogHeader>
        {issues.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {issues.map((issue, i) => (
              <FieldError key={i} issue={issue} />
            ))}
          </div>
        )}
        <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr] gap-4 sm:grid-cols-[13rem_1fr] sm:grid-rows-1">
          <div className="flex max-h-40 min-h-0 flex-col gap-2 sm:max-h-none">
            <nav aria-label="Variables" className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
              {variables.length === 0 && (
                <p className="px-1 text-xs text-muted-foreground">No variables yet.</p>
              )}
              {variables.map((v, i) => (
                <button
                  key={i}
                  type="button"
                  aria-current={i === index}
                  onClick={() => select(i)}
                  className={cn(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50",
                    i === index && "bg-muted font-medium",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">
                    {v.name || <span className="text-muted-foreground">(unnamed)</span>}
                  </span>
                  {hasIssue(v.name) && (
                    <span className="size-2 shrink-0 rounded-full bg-red-600" role="img" aria-label="Has a problem" />
                  )}
                  <span className="shrink-0 text-xs text-muted-foreground">{v.type}</span>
                </button>
              ))}
            </nav>
            <Button type="button" variant="outline" className="h-9" onClick={add}>
              <Plus aria-hidden /> Add variable
            </Button>
          </div>
          <div className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-lg border p-3">
            {current ? (
              <>
                <Labeled id="var-name" label="Name">
                  <Input
                    id="var-name"
                    className="h-10"
                    value={current.name}
                    onChange={(e) => setVariables(patch(variables, index, { name: e.target.value }))}
                  />
                </Labeled>
                <Labeled id="var-type" label="Type">
                  <TypeSelect
                    id="var-type"
                    value={current.type}
                    onChange={(t) =>
                      setVariables(patch(variables, index, { ...typeChange(t), initial: undefined }))
                    }
                  />
                </Labeled>
                {current.type === "enum" && (
                  <Labeled id="var-values" label="Allowed values (comma separated)">
                    <EnumValues
                      key={index}
                      id="var-values"
                      values={current.values}
                      onChange={(values) => setVariables(patch(variables, index, { values }))}
                    />
                  </Labeled>
                )}
                <Labeled id="var-initial" label="Initial value">
                  <TypedValueInput
                    key={index}
                    id="var-initial"
                    type={current.type}
                    values={current.values}
                    value={current.initial}
                    onChange={(initial) => setVariables(patch(variables, index, { initial }))}
                  />
                </Labeled>
                <Button type="button" variant="ghost" size="sm" className="mt-auto self-end" onClick={remove}>
                  <Trash2 aria-hidden /> Remove
                </Button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Add a variable to give your flow somewhere to keep values between nodes.
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
