function Node({
  x,
  y,
  w,
  h,
  title,
  lines,
  icon,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  lines: string[];
  icon: React.ReactNode;
}) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx="9" className="fill-card stroke-border" />
      <g transform={`translate(${x + 12} ${y + 12})`} className="stroke-muted-foreground" fill="none" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        {icon}
      </g>
      <text x={x + 32} y={y + 21} fontSize="13" fontWeight="600" className="fill-foreground">
        {title}
      </text>
      {lines.map((line, i) => (
        <text key={line} x={x + 12} y={y + 38 + i * 12} fontSize="10" className="fill-muted-foreground">
          {line}
        </text>
      ))}
    </g>
  );
}

function Handle({ x, y }: { x: number; y: number }) {
  return <circle cx={x} cy={y} r="3" className="fill-card stroke-muted-foreground" strokeWidth="1.2" />;
}

export function LandingGraph() {
  return (
    <svg
      viewBox="0 0 640 260"
      role="img"
      aria-label="A flow: Start, then an Eligible condition that branches true to Approve and false to Decline, both ending at End"
      className="block h-auto w-full font-sans"
    >
      <defs>
        <pattern id="landing-dots" width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.9" className="fill-muted-foreground/30" />
        </pattern>
      </defs>
      <rect width="640" height="260" className="fill-background" />
      <rect width="640" height="260" fill="url(#landing-dots)" />

      <g fill="none" className="stroke-muted-foreground/60" strokeWidth="1.5">
        <path d="M120 130H156" />
        <path d="M316 114C350 114 350 58 384 58" />
        <path d="M316 146C350 146 350 202 384 202" />
        <path d="M488 58C508 58 508 130 528 130" />
        <path d="M488 202C508 202 508 130 528 130" />
      </g>

      <Node x={16} y={108} w={104} h={44} title="Start" lines={["2 inputs"]} icon={<path d="M3 2.5v9l8-4.5z" />} />
      <Node
        x={156}
        y={96}
        w={160}
        h={68}
        title="Eligible?"
        lines={["income >= 30000 &&", "credit_score >= 600"]}
        icon={
          <>
            <circle cx="3" cy="3" r="1.6" />
            <circle cx="3" cy="11" r="1.6" />
            <circle cx="11" cy="4" r="1.6" />
            <path d="M3 4.6v4.8M11 5.6c0 3-6 1.8-7.4 4" />
          </>
        }
      />
      <text x="308" y="117" textAnchor="end" fontSize="9" className="fill-muted-foreground">
        true
      </text>
      <text x="308" y="149" textAnchor="end" fontSize="9" className="fill-muted-foreground">
        false
      </text>
      <Node
        x={384}
        y={36}
        w={104}
        h={44}
        title="Approve"
        lines={["1 assignment"]}
        icon={<path d="M4 2.5C2 5 2 9 4 11.5M10 2.5c2 2.5 2 6.5 0 9M5.5 5.5l3 3m0-3l-3 3" />}
      />
      <Node
        x={384}
        y={180}
        w={104}
        h={44}
        title="Decline"
        lines={["1 assignment"]}
        icon={<path d="M4 2.5C2 5 2 9 4 11.5M10 2.5c2 2.5 2 6.5 0 9M5.5 5.5l3 3m0-3l-3 3" />}
      />
      <Node x={528} y={108} w={96} h={44} title="End" lines={["1 output"]} icon={<path d="M3 12V2m0 0h8l-2 3 2 3H3" />} />

      {[
        [120, 130],
        [156, 130],
        [316, 114],
        [316, 146],
        [384, 58],
        [384, 202],
        [488, 58],
        [488, 202],
        [528, 130],
      ].map(([x, y]) => (
        <Handle key={`${x}-${y}`} x={x} y={y} />
      ))}
    </svg>
  );
}
