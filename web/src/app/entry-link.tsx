"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

import { authClient } from "@/lib/auth/client";

type Props = Omit<ComponentProps<typeof Link>, "href" | "children"> & {
  signedOutLabel: string;
  signedInLabel: string;
};

// Static HTML always ships the signed-out label; the session check runs after paint.
export function EntryLink({ signedOutLabel, signedInLabel, ...props }: Props) {
  const { data } = authClient.useSession();
  return (
    <Link href={data ? "/flows" : "/login"} {...props}>
      {data ? signedInLabel : signedOutLabel}
    </Link>
  );
}
