import { requireSession } from "@/lib/auth/session";

import { EditorUserProvider } from "./editor-user";

export default async function EditorLayout({ children }: { children: React.ReactNode }) {
  const { user } = await requireSession();
  return (
    <EditorUserProvider name={user.name} email={user.email}>
      <div className="flex flex-1 flex-col">{children}</div>
    </EditorUserProvider>
  );
}
