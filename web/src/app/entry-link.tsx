"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ComponentProps, useEffect, useState, useTransition } from "react";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { WAKING_TEXT } from "@/components/waking-notice";
import { authClient } from "@/lib/auth/client";

type Props = Omit<ComponentProps<typeof Link>, "href" | "children"> & {
  signedOutLabel: string;
  signedInLabel: string;
};

const MODAL_DELAY_MS = 1500;

function WakingDialog() {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), MODAL_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);
  return (
    <Dialog open={visible}>
      <DialogContent showCloseButton={false} role="alertdialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Waking the server
          </DialogTitle>
          <DialogDescription>{WAKING_TEXT}</DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  );
}

// Static HTML always ships the signed-out label; the session check runs after paint.
export function EntryLink({ signedOutLabel, signedInLabel, onClick, ...props }: Props) {
  const { data } = authClient.useSession();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const href = data ? "/overview" : "/login";

  return (
    <>
      <Link
        href={href}
        {...props}
        onClick={(event) => {
          onClick?.(event);
          const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
          if (event.defaultPrevented || modified || event.button !== 0) return;
          event.preventDefault();
          startTransition(() => router.push(href));
        }}
      >
        {data ? signedInLabel : signedOutLabel}
      </Link>
      {pending && <WakingDialog />}
    </>
  );
}
