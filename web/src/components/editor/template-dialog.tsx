"use client";

import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { CatalogGallery, CatalogIcon } from "@/components/catalog/catalog-gallery";
import { openMarketplace } from "@/components/marketplace/store";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { listNodeTemplates } from "@/lib/api/client";
import type { NodeTemplate, NodeTemplateItem } from "@/lib/api/models";
import { call, errorText } from "@/lib/call";
import { prefillHref } from "@/lib/connections";
import { applyTemplate, connectionNeed, GROUPS, isBlank, templateItems } from "@/lib/graph/node-templates";
import type { HttpRequestData } from "@/lib/graph/types";
import { cn } from "@/lib/utils";

import { useEditor } from "./store";

type Loaded =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; items: NodeTemplateItem[] };

let cached: NodeTemplateItem[] | null = null;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  );
}

function AddLink({ template }: { template: NodeTemplate }) {
  const wanted = template.connection;
  if (!wanted) return null;
  return (
    <a
      href={prefillHref(wanted.type, wanted.values ?? {})}
      target="_blank"
      rel="noreferrer"
      className="underline underline-offset-2"
    >
      Add one
    </a>
  );
}

function ConnectionLine({ template }: { template: NodeTemplate }) {
  const connections = useEditor((s) => s.connections);
  const typeNames = useEditor((s) => s.connectionTypeNames);
  const need = connectionNeed(template, connections);
  if (need.kind === "none") return null;
  const typeName = typeNames[template.connection?.type ?? ""] ?? template.connection?.type;
  return (
    <Row label="Connection">
      {need.kind === "picked" && <>Uses your connection “{need.connection.name}”.</>}
      {need.kind === "choose" && <>You have several {need.typeName} connections; pick one in the node afterwards.</>}
      {need.kind === "missing" && (
        <>
          Needs a {typeName} connection. <AddLink template={template} />, then pick it in the node.
        </>
      )}
      {need.kind === "blocked" && (
        <>
          Your {need.typeName} connections do not allow {need.host}. <AddLink template={template} /> that does.
        </>
      )}
    </Row>
  );
}

function Preview({
  template,
  current,
  onBack,
  onApply,
}: {
  template: NodeTemplate;
  current: HttpRequestData;
  onBack: () => void;
  onApply: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const data = template.data;
  const headers = Object.keys(data.headers ?? {});
  const inputs = template.inputs ?? [];
  const secrets = template.secrets ?? [];

  return (
    <div className="flex flex-col gap-4">
      <DialogHeader>
        <button
          type="button"
          onClick={onBack}
          className="flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden /> All templates
        </button>
        <DialogTitle className="flex items-center gap-2">
          <CatalogIcon name={template.icon ?? "plug"} className="size-4" />
          {template.name}
        </DialogTitle>
        <DialogDescription>{template.description}</DialogDescription>
      </DialogHeader>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <Row label="Request">
          <span className="font-mono text-xs">
            {data.method} {data.url}
          </span>
        </Row>
        {headers.length > 0 && <Row label="Headers">{headers.join(", ")}</Row>}
        {data.body_type && data.body_type !== "none" && <Row label="Body">{data.body_type}</Row>}
        <ConnectionLine template={template} />
        {inputs.length > 0 && <Row label="Reads inputs">{inputs.map((i) => i.name).join(", ")}</Row>}
        {secrets.length > 0 && <Row label="Needs secrets">{secrets.join(", ")}</Row>}
      </dl>
      {inputs.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Add these as inputs on the Start node, or change the references in the request.
        </p>
      )}
      {confirming && (
        <p role="alert" className="rounded-lg border border-amber-600/40 p-3 text-sm">
          This replaces the settings already in this request.
        </p>
      )}
      <DialogFooter>
        {confirming ? (
          <>
            <Button type="button" variant="outline" className="h-10" onClick={() => setConfirming(false)}>
              Keep mine
            </Button>
            <Button type="button" className="h-10" onClick={onApply}>
              Replace
            </Button>
          </>
        ) : (
          <Button
            type="button"
            className="h-10"
            onClick={() => (isBlank(current) ? onApply() : setConfirming(true))}
          >
            Use template
          </Button>
        )}
      </DialogFooter>
    </div>
  );
}

// Mounted only while open, so its state starts fresh each time.
export function TemplateDialog({
  onClose,
  current,
  onApply,
}: {
  onClose: () => void;
  current: HttpRequestData;
  onApply: (config: HttpRequestData) => void;
}) {
  const connections = useEditor((s) => s.connections);
  const [loaded, setLoaded] = useState<Loaded>(
    cached ? { state: "ready", items: cached } : { state: "loading" },
  );
  const [attempt, setAttempt] = useState(0);
  const [pickedId, setPickedId] = useState("");

  useEffect(() => {
    if (cached) return;
    let stale = false;
    call(listNodeTemplates({ node_type: "http_request" })).then((result) => {
      if (stale) return;
      if (result.ok) {
        cached = result.data.items;
        setLoaded({ state: "ready", items: result.data.items });
      } else {
        setLoaded({ state: "error", message: errorText(result.error) });
      }
    });
    return () => {
      stale = true;
    };
  }, [attempt]);

  const items = loaded.state === "ready" ? loaded.items : [];
  const picked = items.find((i) => i.template.id === pickedId)?.template;

  function retry() {
    setLoaded({ state: "loading" });
    setAttempt((n) => n + 1);
  }

  // Something was installed or removed, so the cached list is stale.
  function reload() {
    cached = null;
    retry();
  }

  function apply(template: NodeTemplate) {
    onApply(applyTemplate(template, connections, current));
    onClose();
    toast.success(`Applied ${template.name}`);
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className={cn(!picked && "sm:max-w-2xl")}>
        {loaded.state !== "ready" ? (
          <div className="flex flex-col gap-3">
            <DialogHeader>
              <DialogTitle>Use a template</DialogTitle>
              <DialogDescription>Fills in this request. You can change everything afterwards.</DialogDescription>
            </DialogHeader>
            {loaded.state === "loading" ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Loading templates…</p>
            ) : (
              <p role="alert" className="py-6 text-center text-sm text-muted-foreground">
                Could not load templates: {loaded.message}{" "}
                <button type="button" onClick={retry} className="underline">
                  Retry
                </button>
              </p>
            )}
          </div>
        ) : picked ? (
          <Preview
            template={picked}
            current={current}
            onBack={() => setPickedId("")}
            onApply={() => apply(picked)}
          />
        ) : (
          <CatalogGallery
            title="Use a template"
            description="Fills in this request. You can change everything afterwards."
            items={templateItems(items)}
            order={GROUPS}
            footer={
              <button
                type="button"
                onClick={() => openMarketplace({ kinds: ["node-template"], onChanged: reload })}
                className="w-fit text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
              >
                Browse the Marketplace for more
              </button>
            }
            onPick={setPickedId}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
