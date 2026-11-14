import { redirect } from "next/navigation";

export default function StatusPage() {
  redirect("/settings/system");
}
