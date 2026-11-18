"use client";

import { LayoutTemplate } from "lucide-react";
import { Fragment, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SelectField } from "@/components/ui/select-field";
import { Textarea } from "@/components/ui/textarea";
import type { FlowNode } from "@/lib/graph/convert";
import {
  BODY_TYPES,
  type BodyType,
  bodyOnTypeChange,
  headerNameCheck,
  jsonText,
  METHODS,
  type Method,
  type NameCheck,
  parseJson,
  parseTimeout,
  recordOf,
  type Row,
  rowProblem,
  rowsOf,
} from "@/lib/graph/http-request";
import type { HttpRequestData } from "@/lib/graph/types";

import { ExpandableInput } from "./expand-field";
import { ExpressionInput } from "./expression-input";
import { FieldError, Labeled, ListEditor } from "./fields";
import { fieldIssue } from "./issues";
import { useEditor } from "./store";
import { TemplateDialog } from "./template-dialog";

type Update = (patch: Partial<HttpRequestData>) => void;

const SECRETS_HELP = "Use {{ secrets.NAME }} for a credential. A saved value is never shown.";

function KeyValueRows({
  title,
  prefix,
  node,
  rows,
  onChange,
  check,
  caseInsensitive = false,
  secrets,
  issueField,
  namePlaceholder,
  valuePlaceholder,
  addLabel,
  emptyText,
}: {
  title: string;
  prefix: string;
  node: FlowNode;
  rows: Row[];
  onChange: (rows: Row[]) => void;
  check?: NameCheck;
  caseInsensitive?: boolean;
  secrets: boolean;
  issueField: string;
  namePlaceholder: string;
  valuePlaceholder: string;
  addLabel: string;
  emptyText: string;
}) {
  const issues = useEditor((s) => s.issues);
  const patch = (i: number, change: Partial<Row>) =>
    onChange(rows.map((row, j) => (j === i ? { ...row, ...change } : row)));

  return (
    <ListEditor
      title={title}
      items={rows}
      addLabel={addLabel}
      emptyText={emptyText}
      onAdd={() => onChange([...rows, { name: "", value: "" }])}
      onRemove={(i) => onChange(rows.filter((_, j) => j !== i))}
      renderItem={(row, i) => {
        const id = `${node.id}-${prefix}-${i}`;
        const problem = rowProblem(rows, i, check, caseInsensitive);
        const server = fieldIssue(issues, node.id, `${issueField}.${row.name}`);
        return (
          <>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor={`${id}-name`} className="text-xs text-muted-foreground">
                Name
              </Label>
              <Input
                id={`${id}-name`}
                className="h-10 font-mono text-xs"
                value={row.name}
                placeholder={namePlaceholder}
                autoComplete="off"
                spellCheck={false}
                aria-invalid={problem !== null}
                onChange={(e) => patch(i, { name: e.target.value })}
              />
              {problem && (
                <p role="alert" className="text-xs text-red-700 dark:text-red-400">
                  {problem}. This row is not saved until it is fixed.
                </p>
              )}
            </div>
            <Labeled id={`${id}-value`} label="Value" issue={server}>
              <ExpandableInput
                id={`${id}-value`}
                nodeId={node.id}
                title={`${title} ${row.name || i + 1}`}
                value={row.value}
                placeholder={valuePlaceholder}
                secrets={secrets}
                onChange={(value) => patch(i, { value })}
              />
            </Labeled>
          </>
        );
      }}
    />
  );
}

function ConnectionPicker({ node, config, update }: { node: FlowNode; config: HttpRequestData; update: Update }) {
  const connections = useEditor((s) => s.connections);
  const issues = useEditor((s) => s.issues);
  const id = `${node.id}-connection`;
  const chosen = connections.find((c) => c.id === config.connection_id);
  const missing = config.connection_id !== "" && !chosen;
  const server = fieldIssue(issues, node.id, "data.connection_id");

  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-medium">Connection</h3>
      <Labeled id={id} label="Sign requests with" issue={server}>
        <SelectField
          id={id}
          value={chosen ? chosen.id : ""}
          onValueChange={(next) => update({ connection_id: next })}
          options={[
            { value: "", label: "None" },
            ...connections.map((c) => ({ value: c.id, label: `${c.name} (${c.typeName})` })),
          ]}
        />
      </Labeled>
      {chosen && (
        <p className="text-xs text-muted-foreground">
          Adds its credentials to the request, and only for {chosen.hosts || "its allowed hosts"}. A header you set
          below wins over it.
        </p>
      )}
      {missing && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          The saved connection no longer exists. Pick another, or the run will fail.
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        {connections.length === 0 ? "No connections yet. " : ""}
        <a
          href="/connections"
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 hover:text-foreground"
        >
          Manage connections
        </a>
      </p>
    </section>
  );
}

function HeadersEditor({ node, config, update }: { node: FlowNode; config: HttpRequestData; update: Update }) {
  const [rows, setRows] = useState(() => rowsOf(config.headers));
  const change = (next: Row[]) => {
    setRows(next);
    update({ headers: recordOf(next, headerNameCheck, true) });
  };
  return (
    <section className="flex flex-col gap-3">
      <KeyValueRows
        title="Headers"
        prefix="hdr"
        node={node}
        rows={rows}
        onChange={change}
        check={headerNameCheck}
        caseInsensitive
        secrets
        issueField="data.headers"
        namePlaceholder="Authorization"
        valuePlaceholder="Bearer {{ secrets.API_KEY }}"
        addLabel="Add header"
        emptyText="No headers. Add one, or pick a connection above for a credential."
      />
      <p className="text-xs text-muted-foreground">{SECRETS_HELP}</p>
    </section>
  );
}

function QueryEditor({ node, config, update }: { node: FlowNode; config: HttpRequestData; update: Update }) {
  const [rows, setRows] = useState(() => rowsOf(config.query));
  const change = (next: Row[]) => {
    setRows(next);
    update({ query: recordOf(next) });
  };
  return (
    <KeyValueRows
      title="Query parameters"
      prefix="qry"
      node={node}
      rows={rows}
      onChange={change}
      secrets
      issueField="data.query"
      namePlaceholder="customer"
      valuePlaceholder="{{ input.customer_id }}"
      addLabel="Add parameter"
      emptyText="No query parameters. They are added to the URL and encoded for you."
    />
  );
}

function JsonBody({ node, config, update }: { node: FlowNode; config: HttpRequestData; update: Update }) {
  const issues = useEditor((s) => s.issues);
  const [text, setText] = useState(() => jsonText(config.body));
  const [error, setError] = useState<string | null>(null);
  const change = (next: string) => {
    setText(next);
    const parsed = parseJson(next);
    setError(parsed.ok ? null : parsed.error);
    if (parsed.ok) update({ body: parsed.value });
  };
  const id = `${node.id}-json-body`;
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        JSON body
      </Label>
      <Textarea
        id={id}
        rows={8}
        className="font-mono text-xs"
        value={text}
        spellCheck={false}
        aria-invalid={error !== null}
        placeholder={'{ "customer": "{{ input.customer_id }}" }'}
        onChange={(e) => change(e.target.value)}
      />
      {error && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          {error}. The last valid body is kept until this is fixed.
        </p>
      )}
      <FieldError issue={fieldIssue(issues, node.id, "data.body")} />
      <p className="text-xs text-muted-foreground">
        Text values can hold templates. {SECRETS_HELP} A value that is only one reference keeps its type.
      </p>
    </div>
  );
}

function FormBody({ node, config, update }: { node: FlowNode; config: HttpRequestData; update: Update }) {
  const [rows, setRows] = useState(() => rowsOf(config.body as Record<string, string>));
  const change = (next: Row[]) => {
    setRows(next);
    update({ body: recordOf(next) });
  };
  return (
    <KeyValueRows
      title="Form fields"
      prefix="frm"
      node={node}
      rows={rows}
      onChange={change}
      secrets
      issueField="data.body"
      namePlaceholder="client_id"
      valuePlaceholder="{{ secrets.CLIENT_SECRET }}"
      addLabel="Add field"
      emptyText="No fields. Each name and value is encoded for you."
    />
  );
}

function TextBody({ node, config, update }: { node: FlowNode; config: HttpRequestData; update: Update }) {
  const issues = useEditor((s) => s.issues);
  const id = `${node.id}-text-body`;
  return (
    <Labeled id={id} label="Text body" issue={fieldIssue(issues, node.id, "data.body")}>
      <ExpressionInput
        id={id}
        nodeId={node.id}
        kind="template"
        title="Text body"
        secrets
        value={typeof config.body === "string" ? config.body : ""}
        placeholder="<order>{{ input.id }}</order>"
        onChange={(body) => update({ body })}
      />
    </Labeled>
  );
}

function Timeout({ config, update }: { config: HttpRequestData; update: Update }) {
  const [text, setText] = useState(config.timeout_seconds === null ? "" : String(config.timeout_seconds));
  const parsed = parseTimeout(text);
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor="http-timeout" className="text-xs text-muted-foreground">
        Timeout (seconds)
      </Label>
      <Input
        id="http-timeout"
        className="h-10"
        inputMode="numeric"
        value={text}
        placeholder="Server default"
        aria-invalid={!parsed.ok}
        onChange={(e) => {
          setText(e.target.value);
          const next = parseTimeout(e.target.value);
          if (next.ok) update({ timeout_seconds: next.value });
        }}
      />
      {!parsed.ok && (
        <p role="alert" className="text-xs text-red-700 dark:text-red-400">
          {parsed.error}
        </p>
      )}
    </div>
  );
}

export function HttpRequestForm({ node }: { node: FlowNode }) {
  const setConfig = useEditor((s) => s.setNodeConfig);
  const issues = useEditor((s) => s.issues);
  const config = node.data.config as HttpRequestData;
  const update: Update = (patch) => setConfig(node.id, { ...config, ...patch });
  const prefix = `${node.id}-http`;
  const sendsBody = config.method !== "GET";
  const [picking, setPicking] = useState(false);
  // The fields below keep their own row state, so applying a template remounts them.
  const [revision, setRevision] = useState(0);

  return (
    <>
      <Button type="button" variant="outline" className="h-9 w-fit" onClick={() => setPicking(true)}>
        <LayoutTemplate aria-hidden /> Use a template
      </Button>
      {picking && (
        <TemplateDialog
          onClose={() => setPicking(false)}
          current={config}
          onApply={(next) => {
            setConfig(node.id, next);
            setRevision((r) => r + 1);
          }}
        />
      )}
      <Fragment key={revision}>
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Request</h3>
          <Labeled id={`${prefix}-method`} label="Method">
            <SelectField
              id={`${prefix}-method`}
              value={config.method}
              options={METHODS.map((m) => ({ value: m, label: m }))}
              onValueChange={(method) => update({ method: method as Method })}
            />
          </Labeled>
          <Labeled id={`${prefix}-url`} label="URL" issue={fieldIssue(issues, node.id, "data.url")}>
            <ExpandableInput
              id={`${prefix}-url`}
              nodeId={node.id}
              title="URL"
              value={config.url}
              placeholder="https://api.example.com/score"
              onChange={(url) => update({ url })}
            />
          </Labeled>
          <p className="text-xs text-muted-foreground">
            A secret cannot be used in the URL. Put credentials in a header or the body.
          </p>
        </section>
        <ConnectionPicker node={node} config={config} update={update} />
        <HeadersEditor key={`${node.id}-h`} node={node} config={config} update={update} />
        <QueryEditor key={`${node.id}-q`} node={node} config={config} update={update} />
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Body</h3>
          <Labeled id={`${prefix}-body-type`} label="Body type">
            <SelectField
              id={`${prefix}-body-type`}
              value={config.body_type}
              options={BODY_TYPES}
              onValueChange={(next) =>
                update({
                  body_type: next as BodyType,
                  body: bodyOnTypeChange(config.body_type, next as BodyType, config.body),
                })
              }
            />
          </Labeled>
          {!sendsBody && config.body_type !== "none" && (
            <p role="alert" className="text-xs text-red-700 dark:text-red-400">
              A GET request cannot have a body. Pick another method or remove the body.
            </p>
          )}
          {config.body_type === "json" && (
            <JsonBody key={`${node.id}-json`} node={node} config={config} update={update} />
          )}
          {config.body_type === "form" && (
            <FormBody key={`${node.id}-form`} node={node} config={config} update={update} />
          )}
          {config.body_type === "text" && <TextBody node={node} config={config} update={update} />}
        </section>
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-medium">Options</h3>
          <Timeout key={`${node.id}-t`} config={config} update={update} />
          <div className="flex items-start gap-3">
            <Checkbox
              id={`${prefix}-fail`}
              checked={config.fail_on_error_status}
              onCheckedChange={(on) => update({ fail_on_error_status: on === true })}
              className="mt-0.5"
            />
            <div className="flex flex-col">
              <Label htmlFor={`${prefix}-fail`}>Fail the run on an error status</Label>
              <span className="text-xs text-muted-foreground">
                Off keeps a 4xx or 5xx answer as data you can branch on.
              </span>
            </div>
          </div>
        </section>
      </Fragment>
    </>
  );
}
