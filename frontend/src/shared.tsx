import React from "react";

export const icons: Record<string, React.ReactNode> = {
  plus: (
    <>
      <path d="M12 5v14M5 12h14" />
    </>
  ),
  home: (
    <>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5.5 10v10h13V10M9 20v-6h6v6" />
    </>
  ),
  lantern: (
    <>
      <path d="M8 3h8M9 3c0 3-3 4-3 9s3 6 3 9M15 3c0 3 3 4 3 9s-3 6-3 9M7 8h10M7 16h10M8 21h8" />
    </>
  ),
  knowledge: (
    <>
      <circle cx="8" cy="8" r="3" />
      <circle cx="17" cy="7" r="2.5" />
      <circle cx="15" cy="17" r="3" />
      <path d="m10.5 9.5 4.3-1.3M9.7 10.4l3.7 4.4" />
    </>
  ),
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 4 4" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </>
  ),
  arrow: (
    <>
      <path d="M5 12h14M14 7l5 5-5 5" />
    </>
  ),
  back: (
    <>
      <path d="M19 12H5m5 5-5-5 5-5" />
    </>
  ),
  spark: (
    <>
      <path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Z" />
      <path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z" />
    </>
  ),
  source: (
    <>
      <path d="M6 3h9l3 3v15H6z" />
      <path d="M15 3v4h4M9 11h6M9 15h6" />
    </>
  ),
  branch: (
    <>
      <circle cx="6" cy="5" r="2" />
      <circle cx="18" cy="7" r="2" />
      <circle cx="18" cy="18" r="2" />
      <path d="M8 5h2a4 4 0 0 1 4 4v5a4 4 0 0 0 4 4M14 10a3 3 0 0 1 3-3" />
    </>
  ),
  cube: (
    <>
      <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z" />
      <path d="m4 7.5 8 4.5 8-4.5M12 12v9" />
    </>
  ),
  compare: (
    <>
      <path d="M8 4 4 8l4 4M4 8h15M16 20l4-4-4-4M20 16H5" />
    </>
  ),
  close: (
    <>
      <path d="m6 6 12 12M18 6 6 18" />
    </>
  ),
  check: (
    <>
      <path d="m5 12 4 4L19 6" />
    </>
  ),
  alert: (
    <>
      <path d="M12 4 3 20h18L12 4Z" />
      <path d="M12 9v5M12 17h.01" />
    </>
  ),
  play: (
    <>
      <path d="m8 5 11 7-11 7V5Z" />
    </>
  ),
  pause: (
    <>
      <path d="M8 5v14M16 5v14" />
    </>
  ),
  zoom: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="M11 8v6M8 11h6m5 8-3-3" />
    </>
  ),
  chevron: (
    <>
      <path d="m9 6 6 6-6 6" />
    </>
  ),
  minus: <path d="M5 12h14" />,
  fit: (
    <>
      <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
    </>
  ),
  map: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <rect x="12" y="11" width="6" height="5" rx="1" />
    </>
  ),
  history: (
    <>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5M12 7v5l3 2" />
    </>
  ),
  skipStart: (
    <>
      <path d="M6 5v14M18 5 9 12l9 7V5Z" />
    </>
  ),
  skipEnd: (
    <>
      <path d="M18 5v14M6 5l9 7-9 7V5Z" />
    </>
  ),
  prev: <path d="m15 6-6 6 6 6" />,
  next: <path d="m9 6 6 6-6 6" />,
  target: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  expand: (
    <>
      <path d="M12 5v14M5 12h14" />
      <rect x="3" y="3" width="18" height="18" rx="3" />
    </>
  ),
  collapse: (
    <>
      <path d="M5 12h14" />
      <rect x="3" y="3" width="18" height="18" rx="3" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  flag: (
    <>
      <path d="M5 21V4M5 4h11l-2 4 2 4H5" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </>
  ),
};

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {icons[name]}
    </svg>
  );
}

export const Tag = ({ tone, children }: { tone: string; children: React.ReactNode }) => (
  <span className={`tag ${tone}`}>
    <i />
    {children}
  </span>
);

export function InfoBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="info-block">
      <h4>{label}</h4>
      {children}
    </div>
  );
}

export type PolicyAction = "consider" | "investigate" | "archive";
export type EvidencePoint = {
  id: string;
  relevance: number;
  novelty: number;
  graphGap: number;
  action: PolicyAction;
  title: string;
  source: string;
  summary: string;
  shared?: boolean;
};

export const parentEvidence: EvidencePoint[] = [
  {
    id: "ev-contracts",
    relevance: 0.91,
    novelty: 0.58,
    graphGap: 0.42,
    action: "consider",
    title: "Customer commitments support financing",
    source: "Infrastructure financing disclosure",
    summary: "Contracted demand can support access to capital for additional capacity.",
    shared: true,
  },
  {
    id: "ev-gpu",
    relevance: 0.86,
    novelty: 0.44,
    graphGap: 0.31,
    action: "consider",
    title: "GPU commitments support expansion",
    source: "Capacity agreement summary",
    summary: "Committed GPU supply is linked to planned data-center buildout.",
    shared: true,
  },
  {
    id: "ev-power",
    relevance: 0.74,
    novelty: 0.79,
    graphGap: 0.88,
    action: "investigate",
    title: "Power constraints vary by region",
    source: "Regional utility filing",
    summary: "Interconnection timelines may delay deployment even when hardware is available.",
    shared: true,
  },
  {
    id: "ev-risk",
    relevance: 0.78,
    novelty: 0.67,
    graphGap: 0.82,
    action: "investigate",
    title: "Financing risk may concentrate",
    source: "Lender risk commentary",
    summary: "Long-term contracts may shift rather than eliminate demand risk.",
  },
  {
    id: "ev-capex",
    relevance: 0.61,
    novelty: 0.38,
    graphGap: 0.19,
    action: "archive",
    title: "Hyperscaler capital expenditure continues",
    source: "Quarterly market overview",
    summary:
      "Broad capital spending grew, but the passage adds little to the specific relationship.",
  },
  {
    id: "ev-demand",
    relevance: 0.82,
    novelty: 0.52,
    graphGap: 0.36,
    action: "consider",
    title: "Demand remains capacity constrained",
    source: "Cloud provider earnings call",
    summary: "Reported demand exceeds currently deployed accelerator capacity.",
  },
  {
    id: "ev-backlog",
    relevance: 0.68,
    novelty: 0.31,
    graphGap: 0.57,
    action: "archive",
    title: "Backlog indicates future demand",
    source: "Company results release",
    summary: "Backlog is large, but this passage repeats previously accepted reporting.",
  },
  {
    id: "ev-grid",
    relevance: 0.72,
    novelty: 0.84,
    graphGap: 0.92,
    action: "investigate",
    title: "Grid queues delay deployment",
    source: "Interconnection queue study",
    summary: "New facilities face materially different grid connection timelines.",
  },
  {
    id: "ev-stake",
    relevance: 0.88,
    novelty: 0.62,
    graphGap: 0.27,
    action: "consider",
    title: "Equity stakes in cloud partners",
    source: "NVIDIA annual report — investments note",
    summary: "Lists non-marketable equity investments in private companies, including cloud infrastructure partners.",
  },
  {
    id: "ev-collateral",
    relevance: 0.79,
    novelty: 0.71,
    graphGap: 0.74,
    action: "investigate",
    title: "Collateral, not contracts alone",
    source: "Lender commentary on GPU-backed loans",
    summary: "Lenders describe GPUs and contracted revenue jointly as collateral.",
  },
  {
    id: "ev-anchor",
    relevance: 0.84,
    novelty: 0.55,
    graphGap: 0.33,
    action: "consider",
    title: "Anchor customer capacity contract",
    source: "Report on a multi-year capacity contract",
    summary: "A large cloud customer reportedly signed multi-year capacity agreements.",
  },
  {
    id: "ev-concentration",
    relevance: 0.8,
    novelty: 0.6,
    graphGap: 0.7,
    action: "consider",
    title: "Few customers account for most revenue",
    source: "Registration statement — risk factors",
    summary: "A small number of customers account for most revenue.",
  },
  {
    id: "ev-secured",
    relevance: 0.7,
    novelty: 0.8,
    graphGap: 0.85,
    action: "consider",
    title: "Power secured via on-site generation",
    source: "Developer announcement",
    summary: "Developer reports power secured for a new campus through on-site generation.",
  },
];

export const childEvidence: EvidencePoint[] = [
  parentEvidence[0],
  parentEvidence[2],
  parentEvidence[7],
  {
    id: "ev-utility",
    relevance: 0.83,
    novelty: 0.88,
    graphGap: 0.95,
    action: "consider",
    title: "Utility timelines are locally binding",
    source: "Northern Virginia utility plan",
    summary: "Transmission delivery schedules constrain several announced projects.",
  },
  {
    id: "ev-location",
    relevance: 0.69,
    novelty: 0.74,
    graphGap: 0.81,
    action: "investigate",
    title: "Capacity can shift between regions",
    source: "Data-center market analysis",
    summary: "Providers may route expansion toward markets with available power.",
  },
  {
    id: "ev-water",
    relevance: 0.43,
    novelty: 0.81,
    graphGap: 0.28,
    action: "archive",
    title: "Cooling water adds another constraint",
    source: "Municipal planning record",
    summary: "Water availability matters locally but is weakly aligned to this branch objective.",
  },
];

export function projectEvidence(
  point: Pick<EvidencePoint, "relevance" | "novelty" | "graphGap">,
  yaw: number,
  pitch: number,
  zoom: number,
  pan: { x: number; y: number },
) {
  const x = (point.relevance - 0.5) * 390;
  const y = (point.novelty - 0.5) * 390;
  const z = (point.graphGap - 0.5) * 390;
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const rx = x * cy - z * sy;
  const rz = x * sy + z * cy;
  const ry = y * cp - rz * sp;
  return { x: 390 + rx * zoom + pan.x, y: 275 - ry * zoom + pan.y, depth: y * sp + rz * cp };
}

