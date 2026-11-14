import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" aria-hidden className={cn("size-7 shrink-0", className)}>
      <rect width="64" height="64" rx="15" fill="#0b1220" />
      <g fill="none" stroke="#fb7185" strokeWidth="5.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9 32 H19" />
        <polygon points="32,18 46,32 32,46 18,32" />
        <path d="M46 32 H55" />
      </g>
    </svg>
  );
}

export function Logo({ className, markClassName }: { className?: string; markClassName?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5 font-semibold tracking-tight", className)}>
      <LogoMark className={markClassName} />
      Decision Flow
    </span>
  );
}
