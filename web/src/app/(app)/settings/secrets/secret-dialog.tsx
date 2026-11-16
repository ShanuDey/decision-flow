"use client";

import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { putSecret } from "@/lib/api/client";
import { errorToast } from "@/lib/api-error";
import { call } from "@/lib/call";
import {
  NAME_MAX,
  nameProblem,
  normalizeName,
  VALUE_MAX,
  VALUE_MIN,
  valueProblem,
} from "@/lib/secrets";

type Props = { mode: "add"; existing: string[] } | { mode: "replace"; name: string };

export function SecretDialog(props: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(props.mode === "replace" ? props.name : "");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);

  const adding = props.mode === "add";
  const replacing = adding ? props.existing.includes(name) : true;
  const problem = nameProblem(name) ?? valueProblem(value);

  function change(next: boolean) {
    setOpen(next);
    if (!next) {
      setName(props.mode === "replace" ? props.name : "");
      setValue("");
      setVisible(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (problem) return;
    setBusy(true);
    const result = await call(putSecret(name, { value }));
    setBusy(false);
    if (!result.ok) {
      errorToast("Could not save the secret", result.error);
      return;
    }
    change(false);
    toast.success(replacing ? `Replaced ${name}` : `Saved ${name}`);
    router.refresh();
  }

  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogTrigger
        render={
          adding ? (
            <Button className="h-10">Add secret</Button>
          ) : (
            <Button variant="ghost" size="sm">
              Replace
            </Button>
          )
        }
      />
      <DialogContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{adding ? "Add secret" : `Replace ${name}`}</DialogTitle>
            <DialogDescription>
              {adding
                ? "The value is encrypted and cannot be read back."
                : "The new value takes the old one's place. The old value cannot be recovered."}
            </DialogDescription>
          </DialogHeader>
          {adding && (
            <div className="flex flex-col gap-2">
              <Label htmlFor="secret-name">Name</Label>
              <Input
                id="secret-name"
                value={name}
                maxLength={NAME_MAX}
                placeholder="STRIPE_KEY"
                autoFocus
                required
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => setName(normalizeName(e.target.value))}
                className="h-10 font-mono"
              />
              <p className="text-xs text-muted-foreground">
                Capital letters, digits and underscores.
                {replacing && name ? ` ${name} exists and will be replaced.` : ""}
              </p>
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="secret-value">Value</Label>
            <div className="flex gap-2">
              <Input
                id="secret-value"
                type={visible ? "text" : "password"}
                value={value}
                minLength={VALUE_MIN}
                maxLength={VALUE_MAX}
                autoFocus={!adding}
                required
                autoComplete="off"
                spellCheck={false}
                data-1p-ignore
                onChange={(e) => setValue(e.target.value)}
                className="h-10 font-mono"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={visible ? "Hide value" : "Show value"}
                aria-pressed={visible}
                onClick={() => setVisible((current) => !current)}
                className="size-10 shrink-0"
              >
                {visible ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">At least {VALUE_MIN} characters.</p>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={busy || problem !== null} className="h-10">
              {busy ? "Saving…" : replacing ? "Replace" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
