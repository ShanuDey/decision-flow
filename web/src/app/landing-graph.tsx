export function LandingGraph() {
  return (
    <svg
      viewBox="0 0 520 300"
      role="img"
      aria-label="A flow from Input to a condition that branches to Approve or Manual review"
      className="block h-auto w-full"
    >
      <g fill="none" className="stroke-muted-foreground" strokeWidth="1.5">
        <path d="M110 150H160" />
        <path d="M270 150C300 150 300 80 330 80" />
        <path d="M270 150C300 150 300 220 330 220" />
      </g>
      <g fontSize="13" fontWeight="500" className="font-sans">
        <rect x="20" y="128" width="90" height="44" rx="10" className="fill-muted stroke-border" />
        <text x="65" y="155" textAnchor="middle" className="fill-foreground">
          Input
        </text>
        <rect x="160" y="118" width="110" height="64" rx="10" className="fill-muted stroke-foreground" />
        <text x="215" y="145" textAnchor="middle" className="fill-foreground">
          Condition
        </text>
        <text x="215" y="164" textAnchor="middle" fontSize="11" className="fill-muted-foreground font-mono">
          score &gt; 700
        </text>
        <rect x="330" y="56" width="140" height="48" rx="10" className="fill-emerald-100 stroke-emerald-600 dark:fill-emerald-950 dark:stroke-emerald-500" />
        <text x="400" y="84" textAnchor="middle" className="fill-emerald-800 dark:fill-emerald-300">
          Approve
        </text>
        <rect x="330" y="196" width="140" height="48" rx="10" className="fill-amber-100 stroke-amber-600 dark:fill-amber-950 dark:stroke-amber-500" />
        <text x="400" y="224" textAnchor="middle" className="fill-amber-800 dark:fill-amber-300">
          Manual review
        </text>
        <text x="296" y="108" fontSize="11" className="fill-muted-foreground font-mono">
          true
        </text>
        <text x="296" y="204" fontSize="11" className="fill-muted-foreground font-mono">
          false
        </text>
      </g>
    </svg>
  );
}
