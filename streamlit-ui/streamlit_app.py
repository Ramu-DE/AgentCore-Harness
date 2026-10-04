"""
Returns & Refunds Agent — Agentic Workflow + Inline Evals

Shows the complete loop in one view:
  1. User sends a prompt
  2. Agent calls tools (trajectory shown step-by-step)
  3. Eval rules fire automatically against the trajectory
  4. Pass/fail grade displayed inline
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

# ─── Path setup — allow importing from evals/ ─────────────────────────────────

_REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from evals.mocks.tools import (
    TraceRecorder,
    set_recorder,
    order_lookup,
    user_lookup,
    product_lookup,
    find_returned_products,
    process_refund,
    policy_retrieval,
)

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Agentic Eval Demo",
    page_icon="🔄",
    layout="wide",
)

# ─── Dataset ──────────────────────────────────────────────────────────────────

@st.cache_data
def load_dataset() -> list[dict]:
    path = _REPO_ROOT / "evals" / "dataset" / "returns_refunds.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

DATASET = load_dataset()

TOOL_FNS = {
    "order_lookup": order_lookup,
    "user_lookup": user_lookup,
    "product_lookup": product_lookup,
    "find_returned_products": find_returned_products,
    "process_refund": process_refund,
    "policy_retrieval": policy_retrieval,
}

TOOL_EMOJI = {
    "order_lookup":          "📦",
    "user_lookup":           "👤",
    "product_lookup":        "🏷️",
    "find_returned_products":"🔍",
    "process_refund":        "💰",
    "policy_retrieval":      "📜",
}

# ─── Eval logic ───────────────────────────────────────────────────────────────

def run_eval_rules(rec: TraceRecorder, rules: dict) -> list[dict]:
    results = []
    for tool in rules.get("must_call", []):
        passed = rec.was_called(tool)
        results.append({"rule": "must_call", "detail": tool,
                         "passed": passed,
                         "msg": f"{'✅' if passed else '❌'} must call `{tool}`"})
    for tool in rules.get("must_not_call", []):
        passed = not rec.was_called(tool)
        results.append({"rule": "must_not_call", "detail": tool,
                         "passed": passed,
                         "msg": f"{'✅' if passed else '❌'} must NOT call `{tool}`"})
    for first, second in rules.get("order_before", []):
        passed = rec.called_before(first, second)
        results.append({"rule": "order_before", "detail": f"{first} → {second}",
                         "passed": passed,
                         "msg": f"{'✅' if passed else '❌'} `{first}` before `{second}`"})
    return results


def replay_trajectory(scenario: dict) -> tuple[TraceRecorder, list[dict]]:
    """Replay the golden trajectory; return recorder + per-step timing."""
    rec = TraceRecorder()
    set_recorder(rec)
    steps = []
    for step in scenario["recorded_trajectory"]:
        name = step["tool"]
        args = step.get("args", {})
        fn = TOOL_FNS.get(name)
        t0 = time.perf_counter()
        result = fn(**args) if fn else {}
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        steps.append({"name": name, "args": args, "result": result, "ms": elapsed})
    set_recorder(None)
    return rec, steps


def build_response(scenario: dict, rec: TraceRecorder) -> str:
    """Synthesise a plausible agent response from tool results."""
    traj = rec.calls
    parts = []

    refund = rec.result_for("process_refund")
    if refund.get("refund_status") == "PROCESSED":
        parts.append(
            f"✅ **Refund processed** for {refund['customer_id']} — "
            f"**{refund['product_name']}** (was {refund['previous_status']} → now **{refund['new_status']}**)."
        )
        return "\n\n".join(parts)

    orders = rec.result_for("order_lookup")
    if orders.get("error"):
        return f"❌ {orders['error']} — no refund can be issued."

    if orders.get("orders"):
        statuses = {o["product_id"]: o["status"] for o in orders["orders"]}
        lines = [f"- **{pid}**: {s}" for pid, s in statuses.items()]
        parts.append("**Orders found:**\n" + "\n".join(lines))
        for pid, status in statuses.items():
            if status == "DELIVERED":
                parts.append(f"⚠️ Product **{pid}** has status **DELIVERED** — refund not applicable.")
            elif status == "CANCELLED":
                parts.append(f"⚠️ Product **{pid}** has status **CANCELLED** — no refund available.")

    policies = rec.result_for("policy_retrieval")
    if policies.get("results"):
        top = policies["results"][0]
        parts.append(f"**Return policy ({top['country']}):** {top['text']}")

    returned = rec.result_for("find_returned_products")
    if returned.get("returned_products"):
        lines = [f"- {r['customer_id']} / {r['product_name']} ({r['status']})"
                 for r in returned["returned_products"]]
        parts.append("**All returned products:**\n" + "\n".join(lines))

    if not parts:
        hints = scenario.get("expected_response_contains", [])
        return f"Task complete. Keywords expected in response: {', '.join(hints)}."

    return "\n\n".join(parts)


# ─── Header ───────────────────────────────────────────────────────────────────

st.title("🔄 Returns & Refunds Agent")
st.caption(
    "**Agentic workflow + inline evals** — pick a scenario, watch the agent call tools, "
    "then see eval rules graded automatically against the trajectory."
)

st.markdown("---")

# ─── Scenario selector ────────────────────────────────────────────────────────

scenario_labels = {
    f"{ex['id']} · {ex['description']}": ex
    for ex in DATASET
}

col_sel, col_run = st.columns([5, 1])
with col_sel:
    chosen_label = st.selectbox(
        "Choose a scenario (or type your own prompt below)",
        options=list(scenario_labels.keys()),
        index=0,
    )
with col_run:
    st.markdown("<br>", unsafe_allow_html=True)
    run_clicked = st.button("▶ Run", type="primary", use_container_width=True)

selected = scenario_labels[chosen_label]

custom_prompt = st.text_input(
    "Or free-form prompt (uses closest matching scenario's trajectory)",
    placeholder="e.g. Process a refund for C-03's laptop",
)

# Show the prompt that will be used
active_prompt = custom_prompt.strip() if custom_prompt.strip() else selected["prompt"]
st.caption(f"**Prompt:** {active_prompt}")

# If custom prompt, find closest scenario by keyword overlap
if custom_prompt.strip():
    words = set(custom_prompt.lower().split())
    scores = []
    for ex in DATASET:
        ex_words = set(ex["prompt"].lower().split()) | set(ex["description"].lower().split())
        scores.append((len(words & ex_words), ex))
    selected = max(scores, key=lambda x: x[0])[1]
    st.caption(f"↳ Matched to: **{selected['id']}** — {selected['description']}")

st.markdown("---")

# ─── Initialise run state ─────────────────────────────────────────────────────

if "last_run" not in st.session_state:
    st.session_state.last_run = None

if run_clicked:
    rec, steps = replay_trajectory(selected)
    eval_results = run_eval_rules(rec, selected["rules"])
    response = build_response(selected, rec)
    st.session_state.last_run = {
        "scenario": selected,
        "prompt": active_prompt,
        "steps": steps,
        "eval_results": eval_results,
        "response": response,
        "rec_names": rec.names(),
    }

run = st.session_state.last_run

# ─── Results (3 columns) ──────────────────────────────────────────────────────

if run is None:
    st.info("👆 Pick a scenario and click **▶ Run** to see the agentic workflow + eval results.")
else:
    sc     = run["scenario"]
    steps  = run["steps"]
    evals  = run["eval_results"]
    passed = sum(1 for r in evals if r["passed"])
    total  = len(evals)
    all_ok = passed == total

    col_chat, col_traj, col_eval = st.columns([2, 2, 2])

    # ── Column 1: Prompt + Response ───────────────────────────────────────────
    with col_chat:
        st.subheader("💬 Conversation")

        with st.chat_message("user"):
            st.markdown(run["prompt"])

        with st.chat_message("assistant"):
            st.markdown(run["response"])

        st.caption(f"Scenario: `{sc['id']}` · {len(steps)} tool call(s)")

    # ── Column 2: Trajectory ──────────────────────────────────────────────────
    with col_traj:
        st.subheader("🔀 Agent Trajectory")
        st.caption("Tool calls made in order →")

        if not steps:
            st.info("No tools called.")
        else:
            for i, step in enumerate(steps, 1):
                emoji = TOOL_EMOJI.get(step["name"], "🔧")
                with st.container(border=True):
                    st.markdown(f"**Step {i}** &nbsp; {emoji} `{step['name']}`")

                    # Args
                    if step["args"]:
                        args_str = "  ".join(
                            f"`{k}={v}`" for k, v in step["args"].items()
                        )
                        st.markdown(f"**Args:** {args_str}")
                    else:
                        st.markdown("**Args:** *(none)*")

                    # Result — truncated for display
                    result_preview = json.dumps(step["result"], default=str)
                    if len(result_preview) > 160:
                        result_preview = result_preview[:160] + "…"
                    st.code(result_preview, language="json")

                    st.caption(f"⏱ {step['ms']} ms")

        # Trajectory summary arrow chain
        if run["rec_names"]:
            chain = " → ".join(f"`{n}`" for n in run["rec_names"])
            st.markdown(f"**Full chain:** {chain}")

    # ── Column 3: Eval Results ────────────────────────────────────────────────
    with col_eval:
        st.subheader("📊 Eval Results")

        # Overall verdict
        if all_ok:
            st.success(f"✅ {passed}/{total} rules passed")
        else:
            st.error(f"❌ {passed}/{total} rules passed — {total - passed} failure(s)")

        st.markdown("**Rule checks:**")
        for r in evals:
            st.markdown(r["msg"])

        st.markdown("---")
        st.markdown("**Expected keywords in response:**")
        keywords = sc.get("expected_response_contains", [])
        response_lower = run["response"].lower()
        for kw in keywords:
            found = kw.lower() in response_lower
            icon = "✅" if found else "⚠️"
            st.markdown(f"{icon} `{kw}`")

        st.markdown("---")
        st.markdown("**Task description:**")
        st.caption(sc["task_description"])

# ─── All 10 scenarios at a glance ─────────────────────────────────────────────

st.markdown("---")
with st.expander("📋 All 10 golden scenarios"):
    for ex in DATASET:
        rule_counts = (
            f"{len(ex['rules']['must_call'])} must-call · "
            f"{len(ex['rules']['must_not_call'])} must-not-call · "
            f"{len(ex['rules']['order_before'])} ordering"
        )
        traj_chain = " → ".join(s["tool"] for s in ex["recorded_trajectory"])
        st.markdown(
            f"**{ex['id']}** — {ex['description']}  \n"
            f"<small>Trajectory: `{traj_chain}`  ·  Rules: {rule_counts}</small>",
            unsafe_allow_html=True,
        )
        st.markdown("")
