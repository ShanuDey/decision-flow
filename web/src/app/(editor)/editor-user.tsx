"use client";

import { createContext, useContext } from "react";

interface EditorUser {
  name: string;
  email: string;
}

const Ctx = createContext<EditorUser | null>(null);

export function EditorUserProvider({
  name,
  email,
  children,
}: EditorUser & { children: React.ReactNode }) {
  return <Ctx.Provider value={{ name, email }}>{children}</Ctx.Provider>;
}

export function useEditorUser(): EditorUser | null {
  return useContext(Ctx);
}
