import { Heart, Star } from "lucide-react";
import Link from "next/link";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M12 .5a11.5 11.5 0 0 0-3.63 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a10.9 10.9 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.7 5.4-5.27 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="flex items-center justify-between gap-3 border-t px-5 py-4 text-sm text-muted-foreground md:px-8">
      <div className="flex items-center gap-4">
        <span>Decision Flow</span>
        <Link href="/status" className="hover:text-foreground">
          Status
        </Link>
      </div>
      <nav aria-label="Project links" className="flex items-center gap-4">
        <a
          href="https://github.com/ShanuDey/decision-flow"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Star Decision Flow on GitHub"
          title="Star on GitHub"
          className="hover:text-foreground"
        >
          <Star className="size-5" aria-hidden />
        </a>
        <a
          href="https://github.com/sponsors/ShanuDey"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Sponsor on GitHub"
          title="Sponsor"
          className="hover:text-foreground"
        >
          <Heart className="size-5" aria-hidden />
        </a>
        <a
          href="https://github.com/ShanuDey/decision-flow"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Decision Flow on GitHub"
          title="GitHub"
          className="hover:text-foreground"
        >
          <GithubIcon className="size-5" />
        </a>
      </nav>
    </footer>
  );
}
