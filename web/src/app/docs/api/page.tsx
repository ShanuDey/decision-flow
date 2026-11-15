import type { Metadata } from "next";

import { Reference } from "./reference";

export const metadata: Metadata = {
  title: "API reference | Decision Flow",
  description: "Run and manage Decision Flow flows over HTTP with an API key.",
};

export default function ApiDocsPage() {
  return <Reference />;
}
