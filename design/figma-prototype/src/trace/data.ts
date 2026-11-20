import { TraceBuilder } from "./builder";
import type { Lantern, Trace } from "./types";

/*
 * ILLUSTRATIVE investigation traces for the prototype.
 * These are simulated events written to demonstrate the interaction model.
 * They are not backend output and make no factual claims beyond illustration.
 */

export const QUESTION =
  "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity expansion reinforce one another?";

const filing = "SEC EDGAR · illustrative excerpt";

function parentTrace(): Trace {
  const b = new TraceBuilder("parent");

  b.ev("intent", "Research question framed", "The user's question was recorded as the investigation intent.");
  b.n({
    id: "intent",
    kind: "intent",
    label: "Map the capacity feedback loop",
    sub: "Research intent",
    round: 0,
    body: "Understand how NVIDIA investments, GPU cloud customers, and capacity expansion reinforce one another.",
  });

  // ───────────── Round 1 ─────────────
  b.startRound("Map investment & capacity relationships", "Broad exploration");
  b.ev("plan", "Exploration round 1 opened", "Controller planned a broad first round with two search directions.");
  b.n({ id: "r1", kind: "round", label: "Map investment & capacity relationships", sub: "Exploration round 1" });
  b.e("intent", "r1", "order");

  b.ev("search", "Search issued · query A", "“NVIDIA equity investments in GPU cloud providers”");
  b.n({ id: "q1", kind: "query", label: "NVIDIA equity investments in GPU cloud providers", sub: "Search query A", provider: "Web search provider" });
  b.e("r1", "q1", "order");

  b.ev("retrieve", "3 sources returned for query A", "Retrieval provider returned 3 documents; all 3 were kept for extraction.");
  b.n({ id: "g1", kind: "group", label: "Investment disclosures", sub: "3 documents" });
  b.e("q1", "g1", "retrieved");
  b.n({ id: "d1", kind: "doc", parent: "g1", label: "GPU cloud provider registration statement", publisher: filing, origin: "primary", docType: "Regulatory filing" });
  b.n({ id: "d2", kind: "doc", parent: "g1", label: "Coverage of NVIDIA’s stake in a GPU cloud provider", publisher: "Technology news outlet", origin: "derivative", docType: "News article" });
  b.n({ id: "d3", kind: "doc", parent: "g1", label: "NVIDIA annual report — investments note", publisher: "Company annual report · illustrative excerpt", origin: "primary", docType: "Annual report" });
  b.e("d2", "d1", "sharedOrigin", "restates d1");

  b.ev("search", "Search issued · query B", "“GPU cloud provider customer contracts and debt financing”");
  b.n({ id: "q2", kind: "query", label: "GPU cloud customer contracts and debt financing", sub: "Search query B", provider: "Web search provider" });
  b.e("r1", "q2", "order");

  b.ev("retrieve", "4 sources returned for query B", "Retrieval provider returned 4 documents.");
  b.n({ id: "g2", kind: "group", label: "Customers & financing", sub: "4 documents" });
  b.e("q2", "g2", "retrieved");
  b.n({ id: "d4", kind: "doc", parent: "g2", label: "Provider debt facility announcement", publisher: "Company press release", origin: "primary", docType: "Press release" });
  b.n({ id: "d5", kind: "doc", parent: "g2", label: "Lender commentary on GPU-backed loans", publisher: "Trade finance publication", origin: "secondary", docType: "Trade press" });
  b.n({ id: "d6", kind: "doc", parent: "g2", label: "Report on a multi-year capacity contract", publisher: "Business news outlet", origin: "secondary", docType: "News article" });
  b.n({ id: "d7", kind: "doc", parent: "g2", label: "Market overview: hyperscaler capital spending", publisher: "Market research note", origin: "secondary", docType: "Research note" });

  b.ev("extract", "7 passages extracted and scored", "Focus policy scored passages: 4 Consider · 1 Investigate · 1 Archive · 1 provenance-only.");
  b.n({ id: "p1", kind: "passage", parent: "d1", label: "GPU supplier also disclosed as shareholder", text: "Committed GPU supply is linked to planned data-center buildout; the GPU supplier is also disclosed as a shareholder.", policy: "consider", evId: "ev-gpu", relevance: "Directly links supplier investment to capacity plans." });
  b.n({ id: "p2", kind: "passage", parent: "d2", label: "Restates shareholder disclosure", text: "Restates the shareholder disclosure from the registration statement without new detail.", relevance: "Adds no independent evidence; kept for provenance.", coordNote: "Extracted for provenance only. The Focus policy did not score it, so no coordinates were recorded." });
  b.n({ id: "p3", kind: "passage", parent: "d3", label: "Equity stakes in cloud partners", text: "Lists non-marketable equity investments in private companies, including cloud infrastructure partners.", policy: "consider", evId: "ev-stake", relevance: "Independent primary confirmation of the investment relationship." });
  b.n({ id: "p4", kind: "passage", parent: "d4", label: "Contracts cited for debt facility", text: "Contracted customer commitments are cited as supporting a new delayed-draw debt facility for additional capacity.", policy: "consider", evId: "ev-contracts", relevance: "Connects customer demand to the ability to finance expansion." });
  b.n({ id: "p5", kind: "passage", parent: "d5", label: "Collateral, not contracts alone", text: "Lenders describe GPUs and contracted revenue jointly as collateral; contracts alone are not described as sufficient.", policy: "investigate", evId: "ev-collateral", relevance: "Qualifies the contracts → financing relationship." });
  b.n({ id: "p6", kind: "passage", parent: "d6", label: "Anchor customer capacity contract", text: "A large cloud customer reportedly signed multi-year capacity agreements with the provider.", policy: "consider", evId: "ev-anchor", relevance: "Shows contracted demand behind capacity expansion." });
  b.n({ id: "p7", kind: "passage", parent: "d7", label: "Capital spending continues broadly", text: "Broad capital spending grew, but the passage adds little to the specific relationship.", policy: "archive", evId: "ev-capex", relevance: "Too general for this question." });

  b.checkpoint({
    id: "c1",
    short: "C1",
    label: "Round 1 sources retrieved",
    resumable: false,
    forkable: false,
    notResumableReason:
      "This snapshot was saved before evidence evaluation. Only retrieved sources and scored passages were persisted — no controller frontier — so research cannot continue or fork from here. You can still view and compare it.",
    status: "Exploring",
    summary: "7 documents and 7 scored passages persisted. Claims and frontier were not yet recorded.",
    frontier: null,
    recordsClaims: false,
    recordsCoords: true,
  });

  b.ev("evaluate", "Evidence evaluated · round 1", "Passages grouped into 3 claims, 1 relationship and 1 contradiction.");
  b.n({ id: "k1", kind: "claim", label: "NVIDIA is both investor in and supplier to a GPU cloud provider", independent: 2, body: "Two primary disclosures from different companies agree. The news article restates one of them and adds no independent support." });
  b.status("k1", "supported", "Supported by two independent primary disclosures.");
  b.e("p1", "k1", "supports").e("p3", "k1", "supports");
  b.n({ id: "k2", kind: "claim", label: "Long-term customer contracts help providers finance capacity expansion", independent: 1, body: "Customer commitments appear in financing announcements, but most support comes from company-originated material." });
  b.status("k2", "supported", "Supported, but with limited independent confirmation.");
  b.e("p4", "k2", "supports").e("p6", "k2", "supports");
  b.n({ id: "x1", kind: "contradiction", label: "Lenders cite GPU collateral, not contracts alone", body: "Trade-finance commentary describes contracts and hardware jointly as collateral." });
  b.e("p5", "x1", "supports").e("x1", "k2", "contradicts", "qualifies");
  b.n({ id: "k3", kind: "claim", label: "Provider capacity growth drives further GPU purchases", independent: 2, body: "Capacity expansion and supply commitments move together in both primary and secondary sources." });
  b.status("k3", "supported", "Supported across primary and secondary sources.");
  b.e("p1", "k3", "supports").e("p6", "k3", "supports");

  b.ev("relate", "Relationship identified", "Claims k1 and k3 were linked into a reinforcing relationship.");
  b.n({ id: "rel1", kind: "relation", label: "Investment → capacity → GPU demand loop", body: "Investment supports provider capacity; provider capacity creates GPU demand. Recorded as a relationship between claims, not a verified causal mechanism." });
  b.e("k1", "rel1", "supports").e("k3", "rel1", "supports");

  b.ev("question", "Open question identified", "The contradiction on collateral left risk allocation unresolved.");
  b.n({ id: "oq1", kind: "question", label: "Who carries downside risk if contracted demand weakens?" });
  b.status("oq1", "open", "Raised by the collateral contradiction.");
  b.e("x1", "oq1", "raised").e("k2", "oq1", "raised");

  b.checkpoint({
    id: "c2",
    short: "C2",
    label: "Evidence evaluated · round 1",
    resumable: true,
    forkable: true,
    status: "Exploring · decision pending",
    summary: "3 claims, 1 relationship, 1 contradiction and 1 open question recorded.",
    frontier: ["Who carries downside risk if contracted demand weakens?"],
    recordsClaims: true,
    recordsCoords: true,
    why: "The controller continued after this checkpoint because the collateral contradiction left risk allocation unresolved.",
  });

  b.ev("decide", "Decision · continue investigating", "Controller chose to investigate an unresolved relationship.");
  b.n({
    id: "dc1",
    kind: "decision",
    label: "Continue: investigate who carries financing risk",
    outcome: "investigate",
    did: "Requested a narrower follow-up round focused on risk allocation between providers, lenders and customers.",
    rationale: [
      { label: "Trigger", value: "Open question linked to a recorded contradiction" },
      { label: "Frontier", value: "Who carries downside risk if contracted demand weakens?" },
      { label: "Budget used", value: "7 of 24 sources" },
      { label: "Policy signal", value: "1 passage marked Investigate" },
    ],
  });
  ["k1", "k2", "k3", "x1", "oq1"].forEach((id) => b.e(id, "dc1", "considered"));
  b.e("cp-c2", "dc1", "order");

  // ───────────── Round 2 ─────────────
  b.startRound("Who carries the risk?", "Follow-up exploration");
  b.ev("plan", "Exploration round 2 opened", "Round prompted by the open question on downside risk.");
  b.n({ id: "r2", kind: "round", label: "Test who carries financing risk", sub: "Exploration round 2" });
  b.e("dc1", "r2", "order").e("oq1", "r2", "prompted");

  b.ev("search", "Search issued · query C", "“GPU-backed debt facilities: who holds downside risk”");
  b.n({ id: "q3", kind: "query", label: "GPU-backed debt: who holds downside risk", sub: "Follow-up query C", provider: "Web search provider" });
  b.e("r2", "q3", "order").e("oq1", "q3", "prompted");

  b.ev("retrieve", "3 sources returned for query C", "Retrieval provider returned 3 documents, one sharing an origin with a round 1 filing.");
  b.n({ id: "g3", kind: "group", label: "Financing risk", sub: "3 documents" });
  b.e("q3", "g3", "retrieved");
  b.n({ id: "d8", kind: "doc", parent: "g3", label: "Credit rating note on GPU-backed debt", publisher: "Credit rating agency · illustrative", origin: "secondary", docType: "Rating note" });
  b.n({ id: "d9", kind: "doc", parent: "g3", label: "Analyst blog summarizing the rating note", publisher: "Independent analyst blog", origin: "derivative", docType: "Blog post" });
  b.n({ id: "d10", kind: "doc", parent: "g3", label: "Registration statement — risk factors", publisher: filing, origin: "primary", docType: "Regulatory filing" });
  b.e("d9", "d8", "sharedOrigin", "summarizes d8").e("d10", "d1", "sharedOrigin", "same filing");

  b.ev("search", "Search issued · query D", "“GPU cloud customer concentration and contract renewal terms”");
  b.n({ id: "q4", kind: "query", label: "Customer concentration and renewal terms", sub: "Follow-up query D", provider: "Web search provider" });
  b.e("r2", "q4", "order");

  b.ev("retrieve", "2 sources returned for query D", "Retrieval provider returned 2 documents.");
  b.n({ id: "g4", kind: "group", label: "Customer concentration", sub: "2 documents" });
  b.e("q4", "g4", "retrieved");
  b.n({ id: "d11", kind: "doc", parent: "g4", label: "Earnings call — capacity remarks", publisher: "Provider earnings call · illustrative", origin: "primary", docType: "Transcript" });
  b.n({ id: "d12", kind: "doc", parent: "g4", label: "Results release — contracted backlog", publisher: "Company results release", origin: "primary", docType: "Press release" });

  b.ev("extract", "5 passages extracted and scored", "2 Consider · 1 Investigate · 1 Archive · 1 provenance-only.");
  b.n({ id: "p8", kind: "passage", parent: "d8", label: "Lenders exposed if revenue and resale fall", text: "Debt is structured so lenders are exposed if contracted revenue and GPU resale values both fall.", policy: "investigate", evId: "ev-risk", relevance: "Directly addresses the open question on risk allocation." });
  b.n({ id: "p9", kind: "passage", parent: "d9", label: "Claims supplier absorbs unused capacity", text: "Claims the GPU supplier would absorb unused capacity — the rating note it summarizes does not say this.", relevance: "Conflicts with its own source.", coordNote: "Derivative passage kept for provenance; not scored, so no coordinates were recorded." });
  b.n({ id: "p10", kind: "passage", parent: "d10", label: "Few customers account for most revenue", text: "A small number of customers account for most revenue.", policy: "consider", evId: "ev-concentration", relevance: "Bears on who carries demand risk." });
  b.n({ id: "p11", kind: "passage", parent: "d11", label: "Demand exceeds deployed capacity; power timing cited", text: "Reported demand exceeds currently deployed capacity; management cites power delivery timing.", policy: "consider", evId: "ev-demand", relevance: "Introduces power availability as a possible constraint." });
  b.n({ id: "p12", kind: "passage", parent: "d12", label: "Backlog restated", text: "Backlog is large, but this passage repeats previously accepted reporting.", policy: "archive", evId: "ev-backlog", relevance: "Low novelty." });

  b.ev("evaluate", "Evidence evaluated · round 2", "2 new claims, 1 contradiction; one round 1 claim revised.");
  b.n({ id: "k4", kind: "claim", label: "Revenue is concentrated in a few large customers", independent: 2, body: "Supported by the risk-factor disclosure and earnings call remarks." });
  b.status("k4", "supported", "Supported by two primary disclosures.");
  b.e("p10", "k4", "supports").e("p11", "k4", "supports");
  b.n({ id: "k5", kind: "claim", label: "Downside risk is shared with lenders through collateralized debt", independent: 1, body: "One independent rating note supports this; its derivative summary adds no independence." });
  b.status("k5", "mixed", "One independent source; a derivative summary disagrees.");
  b.e("p8", "k5", "supports");
  b.n({ id: "x2", kind: "contradiction", label: "Accounts differ on whether the supplier absorbs unused capacity", body: "A derivative blog claims a supplier backstop that its own source does not state." });
  b.e("p9", "x2", "supports").e("x2", "k5", "contradicts");
  b.status("k2", "qualified", "Revised: contracts support financing alongside GPU collateral, not alone.");
  b.e("p8", "k2", "supports");
  b.status("oq1", "partial", "Lenders and providers share exposure; the supplier’s role is unresolved.");

  b.ev("question", "New open question identified", "An earnings-call passage raised power availability.");
  b.n({ id: "oq2", kind: "question", label: "Is power availability the binding constraint on deployment?" });
  b.status("oq2", "open", "Raised by the earnings-call passage on power timing.");
  b.e("p11", "oq2", "raised");

  b.checkpoint({
    id: "c3",
    short: "C3",
    label: "Evidence evaluated · round 2",
    resumable: true,
    forkable: true,
    status: "Exploring · decision pending",
    summary: "5 claims (1 revised), 2 contradictions, 2 open questions recorded.",
    frontier: [
      "Who carries downside risk? (partially addressed)",
      "Is power availability the binding constraint on deployment?",
    ],
    recordsClaims: true,
    recordsCoords: true,
    why: "The controller continued because a new, high-alignment open question appeared.",
  });

  b.ev("decide", "Decision · continue in a new direction", "Controller opened a round on power availability.");
  b.n({
    id: "dc2",
    kind: "decision",
    label: "Continue: test power availability as a constraint",
    outcome: "investigate",
    did: "Requested a new round on grid interconnection and secured power, a direction not searched before.",
    rationale: [
      { label: "Trigger", value: "New open question raised by an earnings-call passage" },
      { label: "Frontier", value: "Is power availability the binding constraint on deployment?" },
      { label: "Budget used", value: "12 of 24 sources" },
      { label: "Not pursued", value: "Supplier backstop — only a derivative source mentions it" },
    ],
  });
  ["k4", "k5", "x2", "oq1", "oq2"].forEach((id) => b.e(id, "dc2", "considered"));
  b.e("cp-c3", "dc2", "order");

  // ───────────── Round 3 ─────────────
  b.startRound("Is power the bottleneck?", "Follow-up exploration");
  b.ev("plan", "Exploration round 3 opened", "Round prompted by the open question on power availability.");
  b.n({ id: "r3", kind: "round", label: "Test power availability as a constraint", sub: "Exploration round 3" });
  b.e("dc2", "r3", "order").e("oq2", "r3", "prompted");

  b.ev("search", "Search issued · query E", "“Grid interconnection delays for GPU data-center campuses”");
  b.n({ id: "q5", kind: "query", label: "Grid interconnection delays for GPU campuses", sub: "Follow-up query E", provider: "Web search provider" });
  b.e("r3", "q5", "order").e("oq2", "q5", "prompted");

  b.ev("retrieve", "5 sources returned for query E", "2 of 5 were syndicated copies of one study.");
  b.n({ id: "g5", kind: "group", label: "Power & grid", sub: "5 documents" });
  b.e("q5", "g5", "retrieved");
  b.n({ id: "d13", kind: "doc", parent: "g5", label: "Utility integrated resource plan", publisher: "Regional utility filing · illustrative", origin: "primary", docType: "Utility filing" });
  b.n({ id: "d14", kind: "doc", parent: "g5", label: "Interconnection queue study", publisher: "Public research laboratory · illustrative", origin: "secondary", docType: "Study" });
  b.n({ id: "d15", kind: "doc", parent: "g5", label: "Campus delayed awaiting substation work", publisher: "Trade press", origin: "secondary", docType: "Trade press" });
  b.n({ id: "d16", kind: "doc", parent: "g5", label: "Syndicated article restating the queue study", publisher: "News syndication", origin: "derivative", docType: "News article" });
  b.n({ id: "d17", kind: "doc", parent: "g5", label: "Second syndicated restatement", publisher: "News syndication", origin: "derivative", docType: "News article" });
  b.e("d16", "d14", "sharedOrigin", "restates d14").e("d17", "d14", "sharedOrigin", "restates d14");

  b.ev("search", "Search issued · query F", "“AI data-center markets where power has been secured”");
  b.n({ id: "q6", kind: "query", label: "Markets where AI data-center power is secured", sub: "Follow-up query F", provider: "Web search provider" });
  b.e("r3", "q6", "order");

  b.ev("retrieve", "1 source returned for query F", "Retrieval provider returned 1 document.");
  b.n({ id: "g6", kind: "group", label: "Counter-evidence", sub: "1 document" });
  b.e("q6", "g6", "retrieved");
  b.n({ id: "d18", kind: "doc", parent: "g6", label: "Developer announcement: on-site power secured", publisher: "Developer press release", origin: "primary", docType: "Press release" });

  b.ev("extract", "5 passages extracted and scored", "1 Consider · 2 Investigate · 2 provenance-only.");
  b.n({ id: "p13", kind: "passage", parent: "d13", label: "Interconnection timelines delay deployment", text: "Interconnection timelines may delay deployment even when hardware is available.", policy: "investigate", evId: "ev-power", relevance: "Directly addresses the power question." });
  b.n({ id: "p14", kind: "passage", parent: "d14", label: "Grid queues vary by region", text: "New facilities face materially different grid connection timelines across regions.", policy: "investigate", evId: "ev-grid", relevance: "Suggests the constraint is regional." });
  b.n({ id: "p15", kind: "passage", parent: "d15", label: "One campus delayed for substation work", text: "One campus was reportedly delayed pending substation work.", relevance: "Single anecdote.", coordNote: "Not scored by the Focus policy; no coordinates were recorded." });
  b.n({ id: "p16", kind: "passage", parent: "d16", label: "Restates queue study", text: "Restates the queue study’s headline finding.", relevance: "Derivative; adds no independence.", coordNote: "Derivative passage; no coordinates were recorded." });
  b.n({ id: "p18", kind: "passage", parent: "d18", label: "Power secured via on-site generation", text: "Developer reports power secured for a new campus through on-site generation.", policy: "consider", evId: "ev-secured", relevance: "Counter-evidence to a global power constraint." });

  b.ev("evaluate", "Evidence evaluated · round 3", "1 claim and 1 contradiction; derivative coverage added no independence.");
  b.n({ id: "k6", kind: "claim", label: "Grid interconnection delays some regional deployments", independent: 2, body: "Supported regionally by a utility filing and a queue study. Not established as a global constraint." });
  b.status("k6", "regional", "Supported in specific regions only.");
  b.e("p13", "k6", "supports").e("p14", "k6", "supports").e("p15", "k6", "supports");
  b.n({ id: "x3", kind: "contradiction", label: "Other markets report power already secured", body: "A developer announcement reports on-site generation for a new campus." });
  b.e("p18", "x3", "supports").e("x3", "k6", "contradicts", "limits scope");
  b.status("oq2", "partial", "Binding in some regions; the global effect is unresolved.");

  b.ev("question", "Open question identified", "Counter-evidence raised whether capacity can relocate.");
  b.n({ id: "oq3", kind: "question", label: "Can providers relocate capacity to power-available markets?" });
  b.status("oq3", "open", "Raised by the secured-power counter-evidence.");
  b.e("x3", "oq3", "raised");

  b.ev("decide", "Decision · stop with unresolved uncertainty", "Controller stopped and preserved the open questions.");
  b.n({
    id: "dc3",
    kind: "decision",
    label: "Stop with unresolved uncertainty",
    outcome: "stop-uncertain",
    did: "Stopped broad retrieval and preserved three open questions for user-directed research.",
    rationale: [
      { label: "Trigger", value: "Last round added 2 derivative sources; independence gain was low" },
      { label: "Budget used", value: "18 of 24 sources" },
      { label: "Assessment", value: "Remaining budget unlikely to resolve the open questions without a narrower direction" },
      { label: "Still open", value: "Risk allocation (partial) · power constraint (partial) · relocation (open)" },
    ],
  });
  ["k2", "k5", "k6", "x3", "oq1", "oq2", "oq3"].forEach((id) => b.e(id, "dc3", "considered"));

  b.checkpoint({
    id: "c4",
    short: "C4",
    label: "Stopped · final state",
    resumable: true,
    forkable: true,
    status: "Stopped with uncertainty",
    summary: "6 claims, 3 contradictions, 3 open questions. Stopping does not mean the conclusions are verified.",
    frontier: [
      "Who carries downside risk? (partially addressed)",
      "Is power the binding constraint? (regional only)",
      "Can providers relocate capacity to power-available markets?",
    ],
    recordsClaims: true,
    recordsCoords: true,
    why: "The controller stopped because new results were mostly derivative and the remaining budget was unlikely to resolve the open questions.",
  });
  b.e("dc3", "cp-c4", "order");
  return b.build();
}

/** Child lantern that inherits a parent checkpoint. */
function childBase(id: string, objective: string, fromLabel: string) {
  const b = new TraceBuilder(id);
  b.ev("intent", "Branch objective recorded", "The branch objective and inherited context were saved with this Lantern.");
  b.n({ id: "intent", kind: "intent", label: objective, sub: "Branch objective", round: 0 });
  b.ev("inherit", "Parent checkpoint inherited", `Evidence and open questions inherited from ${fromLabel}. The parent is unchanged.`);
  b.n({ id: "inh", kind: "inherited", label: `Inherited from parent · ${fromLabel}`, round: 0, body: "Claims, sources and open questions from the parent checkpoint are available as read-only context." });
  b.e("intent", "inh", "order");
  return b;
}

function powerTrace(): Trace {
  const b = childBase("power", "Do power constraints cap AI capacity expansion?", "C4");
  b.startRound("Map regional power timelines", "Exploration");
  b.ev("plan", "Exploration round 1 opened", "Two directions: utility timelines and capacity relocation.");
  b.n({ id: "r1", kind: "round", label: "Map regional power timelines", sub: "Exploration round 1" });
  b.e("inh", "r1", "order");
  b.ev("search", "Search issued · query A", "“Utility interconnection queue timelines by market”");
  b.n({ id: "q1", kind: "query", label: "Utility interconnection timelines by market", sub: "Search query A", provider: "Web search provider" });
  b.e("r1", "q1", "order");
  b.ev("retrieve", "2 sources returned", "Retrieval provider returned 2 documents.");
  b.n({ id: "g1", kind: "group", label: "Utility timelines", sub: "2 documents" });
  b.e("q1", "g1", "retrieved");
  b.n({ id: "d1", kind: "doc", parent: "g1", label: "Utility transmission plan", publisher: "Regional utility filing · illustrative", origin: "primary", docType: "Utility filing" });
  b.n({ id: "d2", kind: "doc", parent: "g1", label: "Municipal planning record", publisher: "Municipal record", origin: "primary", docType: "Public record" });
  b.ev("search", "Search issued · query B", "“AI campuses relocating to power-available regions”");
  b.n({ id: "q2", kind: "query", label: "Campuses relocating to power-available regions", sub: "Search query B", provider: "Web search provider" });
  b.e("r1", "q2", "order");
  b.ev("retrieve", "1 source returned", "Retrieval provider returned 1 document.");
  b.n({ id: "g2", kind: "group", label: "Relocation", sub: "1 document" });
  b.e("q2", "g2", "retrieved");
  b.n({ id: "d3", kind: "doc", parent: "g2", label: "Data-center market analysis", publisher: "Market research note", origin: "secondary", docType: "Research note" });
  b.ev("extract", "3 passages extracted and scored", "1 Consider · 1 Investigate · 1 Archive.");
  b.n({ id: "p1", kind: "passage", parent: "d1", label: "Utility timelines locally binding", text: "Transmission delivery schedules constrain several announced projects.", policy: "consider", evId: "ev-utility" });
  b.n({ id: "p2", kind: "passage", parent: "d2", label: "Cooling water adds a constraint", text: "Water availability matters locally but is weakly aligned to this objective.", policy: "archive", evId: "ev-water" });
  b.n({ id: "p3", kind: "passage", parent: "d3", label: "Capacity can shift between regions", text: "Providers may route expansion toward markets with available power.", policy: "investigate", evId: "ev-location" });
  b.ev("evaluate", "Evidence evaluated · round 1", "1 claim and 1 open question.");
  b.n({ id: "k1", kind: "claim", label: "Utility timelines are binding in specific markets", independent: 2 });
  b.status("k1", "regional", "Supported for specific markets.");
  b.e("p1", "k1", "supports").e("p2", "k1", "supports");
  b.ev("question", "Open question identified", "Relocation may offset the constraint.");
  b.n({ id: "oq1", kind: "question", label: "Does relocation offset regional power limits?" });
  b.status("oq1", "open", "Raised by the market analysis.");
  b.e("p3", "oq1", "raised");
  b.checkpoint({
    id: "p-c1",
    short: "C1",
    label: "Evidence evaluated · round 1",
    resumable: true,
    forkable: true,
    status: "Researching",
    summary: "1 claim and 1 open question recorded.",
    frontier: ["Does relocation offset regional power limits?"],
    recordsClaims: true,
    recordsCoords: true,
    why: "The controller continued to test relocation.",
  });
  b.ev("decide", "Decision · continue", "Controller requested transmission upgrade schedules.");
  b.n({ id: "dc1", kind: "decision", label: "Continue: test transmission upgrade schedules", outcome: "continue", did: "Requested a second round on transmission upgrades.", rationale: [{ label: "Trigger", value: "Open question on relocation" }, { label: "Budget used", value: "3 of 12 sources" }] });
  ["k1", "oq1"].forEach((id) => b.e(id, "dc1", "considered"));
  b.startRound("Transmission upgrades", "Exploration");
  b.ev("plan", "Exploration round 2 opened", "Round prompted by the relocation question.");
  b.n({ id: "r2", kind: "round", label: "Transmission upgrade schedules", sub: "Exploration round 2" });
  b.e("dc1", "r2", "order").e("oq1", "r2", "prompted");
  b.ev("search", "Search issued · query C", "“Transmission upgrade schedules 2026–2028”");
  b.n({ id: "q3", kind: "query", label: "Transmission upgrade schedules 2026–2028", sub: "Follow-up query C", provider: "Web search provider" });
  b.e("r2", "q3", "order");
  b.ev("pending", "Retrieving sources…", "This Lantern is still researching. New events will appear as they are recorded.");
  b.n({ id: "pend", kind: "pending", label: "Retrieval in progress" });
  b.e("q3", "pend", "order");
  return b.build();
}

function riskTrace(): Trace {
  const b = childBase("risk", "Who ultimately carries demand risk?", "C4");
  b.startRound("Lender and customer exposure", "Exploration");
  b.ev("plan", "Exploration round 1 opened", "Focused on rating methodology and lender exposure.");
  b.n({ id: "r1", kind: "round", label: "Lender and customer exposure", sub: "Exploration round 1" });
  b.e("inh", "r1", "order");
  b.ev("search", "Search issued · query A", "“Rating methodology for GPU-backed debt”");
  b.n({ id: "q1", kind: "query", label: "Rating methodology for GPU-backed debt", sub: "Search query A", provider: "Web search provider" });
  b.e("r1", "q1", "order");
  b.ev("retrieve", "3 sources returned", "Retrieval provider returned 3 documents.");
  b.n({ id: "g1", kind: "group", label: "Rating & lender exposure", sub: "3 documents" });
  b.e("q1", "g1", "retrieved");
  b.n({ id: "d1", kind: "doc", parent: "g1", label: "Rating methodology document", publisher: "Credit rating agency · illustrative", origin: "primary", docType: "Methodology" });
  b.n({ id: "d2", kind: "doc", parent: "g1", label: "Loan syndication summary", publisher: "Trade finance publication", origin: "secondary", docType: "Trade press" });
  b.n({ id: "d3", kind: "doc", parent: "g1", label: "Customer contract termination terms", publisher: filing, origin: "primary", docType: "Regulatory filing" });
  b.ev("evaluate", "Evidence evaluated", "2 claims recorded.");
  b.n({ id: "k1", kind: "claim", label: "Lenders hold most near-term downside exposure", independent: 2 });
  b.status("k1", "supported", "Two independent sources.");
  b.e("d1", "k1", "supports").e("d2", "k1", "supports");
  b.n({ id: "k2", kind: "claim", label: "Customers can exit only under limited conditions", independent: 1 });
  b.status("k2", "supported", "One primary disclosure.");
  b.e("d3", "k2", "supports");
  b.ev("decide", "Decision · stop: evidence sufficient", "Controller stopped under its sufficiency policy.");
  b.n({ id: "dc1", kind: "decision", label: "Stop: evidence sufficient under controller policy", outcome: "stop-sufficient", did: "Stopped because the branch objective was addressed by independent sources.", rationale: [{ label: "Trigger", value: "Objective addressed by 2 independent sources" }, { label: "Budget used", value: "3 of 12 sources" }, { label: "Note", value: "Sufficient under policy is not the same as verified" }] });
  ["k1", "k2"].forEach((id) => b.e(id, "dc1", "considered"));
  b.checkpoint({ id: "r-c1", short: "C1", label: "Completed · final state", resumable: true, forkable: true, status: "Completed", summary: "2 claims recorded; no open questions on the branch objective.", frontier: [], recordsClaims: true, recordsCoords: false, why: "Stopped: evidence sufficient under controller policy." });
  b.e("dc1", "cp-r-c1", "order");
  return b.build();
}

function supplyTrace(): Trace {
  const b = childBase("supply", "Can GPU supply keep pace with capacity commitments?", "C4");
  b.startRound("Supply commitments", "Exploration");
  b.ev("plan", "Exploration round 1 opened", "Focused on supply commitments.");
  b.n({ id: "r1", kind: "round", label: "Supply commitments", sub: "Exploration round 1" });
  b.e("inh", "r1", "order");
  b.ev("search", "Search issued · query A", "“GPU supply allocation to cloud providers”");
  b.n({ id: "q1", kind: "query", label: "GPU supply allocation to cloud providers", sub: "Search query A", provider: "Web search provider" });
  b.e("r1", "q1", "order");
  b.ev("retrieve", "2 sources returned", "Both sources were derivative of one announcement.");
  b.n({ id: "g1", kind: "group", label: "Supply allocation", sub: "2 documents" });
  b.e("q1", "g1", "retrieved");
  b.n({ id: "d1", kind: "doc", parent: "g1", label: "Supply allocation announcement", publisher: "Company press release", origin: "primary", docType: "Press release" });
  b.n({ id: "d2", kind: "doc", parent: "g1", label: "Coverage of the allocation", publisher: "Technology news outlet", origin: "derivative", docType: "News article" });
  b.e("d2", "d1", "sharedOrigin", "restates d1");
  b.ev("question", "Open question identified", "Allocation terms are not disclosed.");
  b.n({ id: "oq1", kind: "question", label: "How is constrained supply allocated across providers?" });
  b.status("oq1", "open", "Allocation terms are not disclosed in retrieved sources.");
  b.e("d1", "oq1", "raised");
  b.ev("decide", "Decision · stop: budget exhausted", "Controller paused; the branch needs direction.");
  b.n({ id: "dc1", kind: "decision", label: "Stop: research budget exhausted", outcome: "stop-budget", did: "Paused and asked for user direction.", rationale: [{ label: "Trigger", value: "Branch budget of 6 sources reached" }, { label: "Still open", value: "Allocation terms" }] });
  b.e("oq1", "dc1", "considered");
  b.checkpoint({ id: "s-c1", short: "C1", label: "Paused · awaiting direction", resumable: true, forkable: true, status: "Waiting for input", summary: "1 open question; budget exhausted.", frontier: ["How is constrained supply allocated across providers?"], recordsClaims: true, recordsCoords: false, why: "Stopped because the research budget was exhausted." });
  b.e("dc1", "cp-s-c1", "order");
  return b.build();
}

/** Trace for a user-created fork. "investigate" forks get simulated events revealed live. */
export function forkTrace(lantern: Lantern, parent: Trace): Trace {
  const cp = parent.checkpoints.find((c) => c.id === lantern.fromCheckpoint);
  const claim = parent.nodes.find((n) => n.id === lantern.attachedClaim);
  const b = childBase(lantern.id, lantern.objective, cp ? cp.short : "parent");
  if (claim) {
    b.n({ id: "att", kind: "claim", label: claim.label, round: 0, body: "Claim attached from the parent investigation as the subject of this branch.", history: claim.history?.filter((h) => !cp || h.at <= cp.seq).map((h) => ({ ...h, at: 0 })), independent: claim.independent });
    b.e("inh", "att", "order");
  }
  if (lantern.createdMode !== "investigate") return b.build();
  b.startRound("Seek independent confirmation", "Exploration");
  b.ev("plan", "Exploration round 1 opened", "Round targets sources that do not originate from company disclosures.");
  b.n({ id: "r1", kind: "round", label: "Seek independent confirmation", sub: "Exploration round 1" });
  b.e(claim ? "att" : "inh", "r1", "order");
  b.ev("search", "Search issued · query A", "“Independent analysis of contract-backed GPU financing”");
  b.n({ id: "q1", kind: "query", label: "Independent analysis of contract-backed financing", sub: "Search query A", provider: "Web search provider" });
  b.e("r1", "q1", "order");
  b.ev("search", "Search issued · query B", "“Lender requirements beyond customer contracts”");
  b.n({ id: "q2", kind: "query", label: "Lender requirements beyond customer contracts", sub: "Search query B", provider: "Web search provider" });
  b.e("r1", "q2", "order");
  b.ev("retrieve", "2 sources returned for query A", "Retrieval provider returned 2 documents.");
  b.n({ id: "g1", kind: "group", label: "Independent analysis", sub: "2 documents" });
  b.e("q1", "g1", "retrieved");
  b.n({ id: "d1", kind: "doc", parent: "g1", label: "Academic working paper on GPU-backed lending", publisher: "University working paper · illustrative", origin: "secondary", docType: "Working paper" });
  b.n({ id: "d2", kind: "doc", parent: "g1", label: "Bank credit commentary", publisher: "Bank research · illustrative", origin: "secondary", docType: "Research note" });
  b.ev("retrieve", "1 source returned for query B", "Retrieval provider returned 1 document.");
  b.n({ id: "g2", kind: "group", label: "Lender requirements", sub: "1 document" });
  b.e("q2", "g2", "retrieved");
  b.n({ id: "d3", kind: "doc", parent: "g2", label: "Loan covenant summary", publisher: "Trade finance publication", origin: "secondary", docType: "Trade press" });
  b.ev("evaluate", "Evidence evaluated · round 1", "Independent sources qualify the attached claim.");
  b.n({ id: "k1", kind: "claim", label: "Independent sources tie financing to collateral and contracts jointly", independent: 2 });
  b.status("k1", "supported", "Two independent secondary sources.");
  b.e("d1", "k1", "supports").e("d2", "k1", "supports");
  if (claim) b.e("k1", "att", "contradicts", "qualifies");
  b.ev("pending", "Researching…", "This Lantern is still researching in the simulated prototype.");
  b.n({ id: "pend", kind: "pending", label: "Evaluating lender requirements" });
  b.e("k1", "pend", "order");
  return b.build();
}

export const TRACES: Record<string, Trace> = {
  parent: parentTrace(),
  power: powerTrace(),
  risk: riskTrace(),
  supply: supplyTrace(),
};

export const INITIAL_LANTERNS: Lantern[] = [
  { id: "parent", title: "NVIDIA’s infrastructure investment loop", objective: QUESTION, status: "stopped-uncertain" },
  { id: "power", title: "Do power constraints cap capacity?", objective: "Do power constraints cap AI capacity expansion?", status: "researching", parentId: "parent", fromCheckpoint: "c4", slot: 0 },
  { id: "risk", title: "Who ultimately carries demand risk?", objective: "Who ultimately carries demand risk?", status: "completed", parentId: "parent", fromCheckpoint: "c4", slot: 1 },
  { id: "supply", title: "Can GPU supply keep pace?", objective: "Can GPU supply keep pace with capacity commitments?", status: "awaiting", parentId: "parent", fromCheckpoint: "c4", slot: 2 },
];

export function summarize(trace: Trace, upTo = Infinity) {
  const vis = trace.nodes.filter((n) => n.revealAt <= upTo);
  const count = (k: string) => vis.filter((n) => n.kind === k).length;
  return {
    rounds: trace.rounds.filter((r) => vis.some((n) => n.kind === "round" && n.round === r.n)).length,
    queries: count("query"),
    sources: count("doc"),
    passages: count("passage"),
    claims: count("claim"),
    contradictions: count("contradiction"),
    questions: vis.filter((n) => n.kind === "question").length,
    openQuestions: vis.filter((n) => n.kind === "question" && (n.history?.filter((h) => h.at <= upTo).slice(-1)[0]?.status ?? "open") !== "resolved").length,
    checkpoints: trace.checkpoints.filter((c) => c.seq <= upTo).length,
  };
}

export const STATUS_META: Record<string, { tone: string; label: string }> = {
  "stopped-uncertain": { tone: "amber", label: "Stopped with uncertainty" },
  researching: { tone: "violet", label: "Researching" },
  completed: { tone: "teal", label: "Completed" },
  awaiting: { tone: "amber", label: "Waiting for input" },
  "not-started": { tone: "gray", label: "Saved · not started" },
};
