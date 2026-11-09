import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Decision Flow</h1>
      <Link href="/status" className="underline underline-offset-4">
        System status
      </Link>
    </main>
  );
}
