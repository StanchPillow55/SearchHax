"""Backend-backed UI for the FrontierGraph exploration API.

This is the user-facing surface for the integrated pipeline. Unlike app.py
(which runs the focus ranker standalone), every action here calls the running
exploration backend over HTTP, so the displayed results come from real
retrieval, extraction, exact-quote verification, provenance, knowledge-value
scoring, focus ranking, and the convergence decision.

Run:
    pip install streamlit pandas requests
    exploration/.venv/bin/uvicorn exploration.backend.main:app --port 8000   # backend
    streamlit run focus/ui_backend.py                                        # this UI
"""

from __future__ import annotations

import json
import os

import pandas as pd
import requests
import streamlit as st

from lantern_workspace import render_lantern_workspace

DEFAULT_API = os.environ.get("EXPLORATION_API", "http://127.0.0.1:8000")

# A ready-made read-only profile. Attaching it turns on knowledge-value scoring
# of live candidates and seeds the profile's unresolved interests as open
# questions the controller can act on.
AI_PROFILE = {
    "id": "profile_ai_infrastructure",
    "interests": ["AI systems", "GPUs", "data-center capacity", "semiconductor", "advanced packaging"],
    "goals": ["Track GPU supply across AI systems", "Follow data-center capacity"],
    "unresolved_interests": ["advanced packaging"],
    "known_claims": [
        {"id": "claim_nvidia_coreweave", "subject": "NVIDIA", "predicate": "invested_in",
         "object": "CoreWeave", "text": "NVIDIA invested in CoreWeave."},
        {"id": "claim_capacity_expansion", "subject": "capacity expansion", "predicate": "expansion_status",
         "object": "under investigation", "text": "Capacity expansion is under investigation."},
    ],
    "notes": "Static read-only fixture profile.",
}

st.set_page_config(page_title="FrontierGraph", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="stMainBlockContainer"] { padding-top: 0.75rem; padding-bottom: 0.5rem; max-width: 100%; }
    [data-testid="stHeader"] { background: transparent; }
    @media (max-width: 960px) {
      [data-testid="stMain"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
      [data-testid="stMain"] [data-testid="stColumn"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("FrontierGraph")
st.caption(
    "Every panel below comes from the exploration backend: real retrieval, extraction, "
    "exact-quote verification, provenance, knowledge value, focus, and convergence. "
    "Attention and knowledge value are ranking signals, not factual confidence."
)

DEFAULT_QUESTION = (
    "How do NVIDIA's investments, GPU infrastructure customers, and AI capacity "
    "expansion reinforce one another?"
)


def _get(path: str):
    r = requests.get(f"{api}{path}", timeout=120)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict | None = None):
    r = requests.post(f"{api}{path}", json=body or {}, timeout=300)
    r.raise_for_status()
    return r.json()


def _health() -> bool:
    try:
        requests.get(f"{api}/openapi.json", timeout=5).raise_for_status()
        return True
    except Exception:
        return False


def _run_investigation() -> None:
    """Button callback. Runs once per click and commits exactly one export.

    Reading the widget values here (inside the callback) avoids the Streamlit
    rerun race where a stale run mode from an earlier rerun gets used.
    """
    is_offline = st.session_state["run_mode"].startswith("Offline")
    st.session_state["last_error"] = None
    try:
        if is_offline:
            export = _post("/api/exploration/fixtures/story-c")
        else:
            body = {"question": st.session_state["question"]}
            if st.session_state["use_profile"]:
                body["profile"] = AI_PROFILE
            inv = _post("/api/exploration/investigations", body)
            inv_id = inv["id"]
            _post(f"/api/exploration/investigations/{inv_id}/step")
            export = _post(f"/api/exploration/investigations/{inv_id}/step")
        st.session_state["export"] = export
        st.session_state["ran_mode"] = "offline" if is_offline else "live"
        st.query_params["investigation"] = export["investigation"]["id"]
    except requests.HTTPError as exc:
        st.session_state["last_error"] = f"Backend error: {exc.response.status_code} {exc.response.text[:400]}"
    except Exception as exc:
        st.session_state["last_error"] = f"Run failed: {exc}"


with st.sidebar:
    api = st.text_input("Backend API", DEFAULT_API)
    st.markdown("**Controller**")
    st.caption("Stop/search decisions come from the focus-backed convergence endpoint on the backend.")
    use_profile = st.checkbox(
        "Attach research profile (enables knowledge value)", value=True, key="use_profile",
        help="With a profile, each live candidate also gets a knowledge-value score and the profile's open interests become questions.",
    )
    st.markdown("**Run mode**")
    run_mode = st.radio(
        "What to run",
        ["Offline Story C fixture (free, ignores the question)", "Live web investigation (billable, uses the question)"],
        index=0,
        key="run_mode",
        help="Story C is a fixed provenance demo. The live mode uses your question and makes real Telem/Tavily/LLM calls.",
    )
    offline = run_mode.startswith("Offline")
    if offline:
        st.caption("Run mode is Offline Story C, so this question is not used for this run.")
    else:
        st.caption("Live mode uses the question box. With a profile attached, candidates also get knowledge value.")
    if use_profile:
        with st.expander("Profile being attached"):
            st.json(AI_PROFILE)
    st.text_area(
        "Research question (immutable once created)",
        DEFAULT_QUESTION,
        key="question",
        height=90,
        help="Used only in live mode. Story C runs its own fixed question.",
    )
    st.button("Run investigation", type="primary", on_click=_run_investigation, use_container_width=True)


if not _health():
    st.error(f"Backend not reachable at {api}. Start uvicorn on that address first.")

if st.session_state.get("last_error"):
    st.error(st.session_state["last_error"])

requested = st.query_params.get("investigation")
export = st.session_state.get("export")
if requested and (not export or export["investigation"]["id"] != requested):
    try:
        export = _get(f"/api/exploration/investigations/{requested}")
        st.session_state["export"] = export
    except Exception as exc:
        st.session_state["last_error"] = f"Could not restore investigation: {exc}"
        export = export if export else None
if not export:
    st.info("Set a question and click Run. Keep the offline box checked for a free, deterministic demo.")
    st.stop()

inv = export["investigation"]
usage = inv["usage"]


def _run_followup() -> None:
    q = st.session_state.get("followup_q", "").strip()
    st.session_state["last_error"] = None
    if not q:
        st.session_state["last_error"] = "Enter a follow-up question first."
        return
    try:
        body = {"question": q}
        prior_profile = st.session_state["export"].get("profile")
        if prior_profile:
            body["profile"] = prior_profile
        parent_id = st.session_state["export"]["investigation"]["id"]
        new_inv = _post("/api/exploration/investigations", body)
        inv_id = new_inv["id"]
        _post(f"/api/exploration/investigations/{inv_id}/step")
        new_export = _post(f"/api/exploration/investigations/{inv_id}/step")
        st.session_state["export"] = new_export
        st.session_state["followup_parent"] = parent_id
    except requests.HTTPError as exc:
        st.session_state["last_error"] = f"Follow-up error: {exc.response.status_code} {exc.response.text[:300]}"
    except Exception as exc:
        st.session_state["last_error"] = f"Follow-up failed: {exc}"


actual_mode = inv.get("metadata", {}).get("mode")
if st.session_state.get("followup_parent"):
    st.info(
        f"You are viewing a follow-up investigation. It was started from a previous "
        f"question and is a new, separate investigation (the original question is immutable)."
    )
st.caption(f"{actual_mode} run · {inv['question']}")

with st.expander("Ask a follow-up question", expanded=False):
    st.caption("Starts a new linked investigation. Live follow-ups are billable.")
    open_qs_top = [q["text"] for q in export.get("unresolved_questions", [])]
    fu_cols = st.columns([3, 1])
    with fu_cols[0]:
        st.text_input(
            "Follow-up question",
            value=(open_qs_top[0] if open_qs_top else ""),
            key="followup_q",
            label_visibility="collapsed",
            placeholder="Type a follow-up question, or pick a suggested one below",
        )
    with fu_cols[1]:
        st.button("Run follow-up", type="primary", on_click=_run_followup, use_container_width=True)
    if open_qs_top:
        st.caption("Open questions: " + " · ".join(open_qs_top[:3]))

render_lantern_workspace(export, api)

with st.expander("Investigation records", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", inv["status"])
    c2.metric("Stop reason", inv.get("stop_reason") or "-")
    c3.metric("Decision source", inv.get("decision_source") or "-")
    c4.metric("Searches", usage.get("search_calls", 0))
    if inv.get("decision_source") == "fallback":
        st.warning("Decision came from the labeled fallback, not the convergence controller.")
    elif inv.get("decision_source") == "convergence":
        st.success("Decision came from the focus-backed convergence controller.")
    if inv.get("decision_rationale"):
        st.caption(f"Controller rationale: {inv['decision_rationale']}")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Provider calls", usage.get("provider_calls", 0))
    m2.metric("URLs fetched", usage.get("urls_fetched", 0))
    m3.metric("LLM calls", usage.get("llm_calls", 0))
    m4.metric("LLM tokens", usage.get("llm_tokens") if usage.get("llm_tokens") is not None else "-")
    m5.metric("Network calls", usage.get("network_calls", 0))


    def _generate_answer() -> None:
        inv_id = st.session_state["export"]["investigation"]["id"]
        st.session_state["last_error"] = None
        try:
            st.session_state["export"] = _post(f"/api/exploration/investigations/{inv_id}/answer")
        except requests.HTTPError as exc:
            st.session_state["last_error"] = f"Answer error: {exc.response.status_code} {exc.response.text[:300]}"
        except Exception as exc:
            st.session_state["last_error"] = f"Answer failed: {exc}"


    st.subheader("Answer")
    answer = export.get("answer")
    if answer and not answer.get("blocked") and answer.get("markdown"):
        st.markdown(answer["markdown"])
        st.caption(
            f"Synthesized by {answer.get('model') or 'the answer model'} from the evidence above. "
            f"Tokens: {answer.get('llm_tokens')}. This explains verified evidence; it is not a new verification step."
        )
    elif answer and answer.get("blocked"):
        st.warning(f"Answer not generated: {answer.get('blocker')}")
    else:
        st.caption("No answer generated yet. Generating one makes a billable answer-model call.")
        st.button("Generate cited answer", on_click=_generate_answer)

    supported = [r for r in export["relationships"] if r.get("status") == "supported"]
    st.subheader(f"Supported facts (exact-quote verified) — {len(supported)}")
    if supported:
        st.dataframe(
            pd.DataFrame([
                {"subject": r.get("subject_name", ""), "predicate": r.get("predicate", ""),
                 "object": r.get("object_name", ""), "on pages": len(r.get("source_document_ids") or [])}
                for r in supported
            ]),
            use_container_width=True, hide_index=True,
        )
        st.caption("Each supported fact is grounded in an exact substring of a fetched page.")
    else:
        st.info("No quote-verified supported facts in this run.")

    profile = export.get("profile")
    if profile:
        st.subheader("Attestations (profile priors, not sourced evidence)")
        st.caption("These are read-only profile claims. They are kept separate from supported facts above.")
        st.dataframe(
            pd.DataFrame([
                {"subject": c["subject"], "predicate": c["predicate"], "object": c["object"]}
                for c in profile.get("known_claims", [])
            ]),
            use_container_width=True, hide_index=True,
        )

    st.subheader("Candidates: query attention vs knowledge value")
    rows = []
    for cand in export["candidates"]:
        kv = cand.get("knowledge_value")
        rows.append({
            "title": cand["title"][:60],
            "attention": round(cand["attention"]["score"], 3),
            "knowledge_value": round(kv["score"], 3) if kv else None,
            "KV bridge": (kv.get("bridge_trigger") if kv else None),
            "bridge terms": ", ".join(kv.get("bridge_terms") or []) if kv else "",
            "url": cand["url"],
        })
    cand_df = pd.DataFrame(rows)
    if not cand_df.empty:
        st.dataframe(cand_df, use_container_width=True, hide_index=True)
        if cand_df["knowledge_value"].notna().any():
            top_att = cand_df.sort_values("attention", ascending=False).iloc[0]
            top_kv = cand_df.sort_values("knowledge_value", ascending=False).iloc[0]
            if top_att["url"] != top_kv["url"]:
                st.success(
                    "Knowledge value surfaced a different top candidate than query attention, "
                    "reflecting the attached profile."
                )
                st.caption(
                    f"Top by attention: {top_att['title']} | "
                    f"Top by knowledge value: {top_kv['title']} (bridge: {top_kv['KV bridge']})"
                )
        else:
            st.caption("No profile attached, so candidates carry only the query-attention score.")

    if export.get("contradictions"):
        st.subheader("Contradictions")
        st.dataframe(
            pd.DataFrame([
                {"subject": x["subject_name"], "predicate": x["predicate"],
                 "supported": x["supported_object"], "conflicting": x["conflicting_object"]}
                for x in export["contradictions"]
            ]),
            use_container_width=True, hide_index=True,
        )

    with st.expander("Provenance (per document)"):
        st.dataframe(
            pd.DataFrame([
                {"document": p["document_id"][-8:], "provider": p.get("provider"),
                 "origin kind": p.get("origin_kind"), "origin id": p.get("origin_id")}
                for p in export["provenance"]
            ]),
            use_container_width=True, hide_index=True,
        )

    with st.expander("Open questions"):
        for q in export["unresolved_questions"]:
            st.write(f"- [{q['kind']}] {q['text']}")

    with st.expander("Checkpoints"):
        st.write(f"{len(export.get('checkpoints', []))} checkpoint(s) persisted.")
        for cp in export.get("checkpoints", []):
            st.caption(f"step {cp['step']} ({cp.get('stop_reason') or 'running'}): {cp.get('summary', '')}")

    with st.expander("Raw export JSON"):
        st.code(json.dumps(export, indent=2)[:20000], language="json")


    if st.session_state.get("followup_parent"):
        st.caption(f"This result is linked from investigation {st.session_state['followup_parent']}.")
