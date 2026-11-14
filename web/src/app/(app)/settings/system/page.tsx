import type { Metadata } from "next";

import { StatusCard } from "./status-card";

export const metadata: Metadata = { title: "System · Decision Flow" };

export default function SystemPage() {
  return <StatusCard />;
}
