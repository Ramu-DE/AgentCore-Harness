"""
Eval Dashboard — visualises offline and live eval run history.

Shows:
  - Config status (which env vars / API keys are present)
  - Pass-rate trend over all saved runs
  - Latest run: per-test-case results with trajectory and rule breakdown
  - Run button to trigger a fresh offline eval from the UI
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ─── Paths ────────────────────────────────────────────────────────────────────

_REPO_ROOT    = Path(__file__).parents[2]
_RESULTS_DIR  = _REPO_ROOT / "evals" / "results"
_RUNNER       = _REPO_ROOT / "evals" / "run_evals.py"
_DATASET_FILE = _REPO_ROOT / "evals" / "dataset" / "returns_refunds.jsonl"

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Eval Dashboard",
    page_icon="📊",
    layout="wide",
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=5)
def load_runs() -> list[dict]:
    """Load all saved eval run JSON files, sorted newest-first."""
    runs = []
    for f in sorted(_RESULTS_DIR.glob("run_*.json"), reverse=True):
        try:
            runs.append(json.loads(f.read_text()))
        except Exception:
            pass
    return runs


def load_dataset() -> list[dict]:
    if not _DATASET_FILE.exists():
        return []
    return [json.loads(line) for line in _DATASET_FILE.read_text().splitlines() if line.strip()]


def fmt_ts(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%b %d  %H:%M UTC")
    except Exception:
        return iso


def badge(passed: bool) -> str:
    return "✅ Pass" if passed else "❌ Fail"


def rule_icon(passed: bool) -> str:
    return "✓" if passed else "✗"


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📊 Eval Dashboard")
    st.markdown("---")

    # ── Config status ──────────────────────────────────────────────────────
    st.markdown("### 🔑 Config Status")

    REQUIRED_VARS: list[tuple[str, str, bool]] = [
        ("AWS_DEFAULT_REGION",       "AWS region",              True),
        ("AWS_ACCESS_KEY_ID",        "AWS credentials",         True),
        ("GATEWAY_URL",              "AgentCore gateway URL",   True),
        ("GATEWAY_CLIENT_ID",        "Gateway OAuth client",    True),
        ("GATEWAY_CLIENT_SECRET",    "Gateway OAuth secret",    True),
        ("DEEPEVAL_API_KEY",         "DeepEval cloud",          False),
        ("LANGFUSE_PUBLIC_KEY",      "Langfuse tracing",        False),
        ("AGENT_RUNTIME_ARN",        "AgentCore runtime ARN",   True),
    ]

    for var, label, required in REQUIRED_VARS:
        present = bool(os.environ.get(var))
        icon    = "🟢" if present else ("🔴" if required else "⚪")
        suffix  = " *(required)*" if required and not present else ""
        st.markdown(f"{icon} `{var}`{suffix}  \n<small>{label}</small>", unsafe_allow_html=True)

    st.markdown("---")
    st.caption(
        "Copy `.env.example` → `.env` and fill in missing values.  \n"
        "Required keys (🔴) needed for live eval + chat UI."
    )

# ─── Main layout ──────────────────────────────────────────────────────────────

st.title("📊 Agentic Eval Dashboard")
st.caption("Returns & Refunds Assistant · Offline trajectory rules + live DeepEval metrics")

# ── Top KPI row ───────────────────────────────────────────────────────────────
runs = load_runs()

col1, col2, col3, col4 = st.columns(4)

if runs:
    latest = runs[0]
    prev   = runs[1] if len(runs) > 1 else None

    delta_str = ""
    if prev:
        delta = (latest["pass_rate"] - prev["pass_rate"]) * 100
        delta_str = f"{delta:+.1f}% vs prev"

    col1.metric("Latest pass rate",   f"{latest['pass_rate']*100:.1f}%", delta_str)
    col2.metric("Tests in latest run", str(latest["total"]))
    col3.metric("Failures (latest)",  str(latest["failed"]),
                delta=str(-latest["failed"]) if latest["failed"] == 0 else None)
    col4.metric("Total runs saved",   str(len(runs)))
else:
    col1.metric("Latest pass rate",    "—")
    col2.metric("Tests in latest run", "—")
    col3.metric("Failures (latest)",   "—")
    col4.metric("Total runs saved",    "0")

st.markdown("---")

# ── Pass-rate trend ───────────────────────────────────────────────────────────
st.subheader("Pass-rate trend")

if len(runs) >= 2:
    chart_data = [
        {"Run": fmt_ts(r["run_at"]), "Pass rate (%)": round(r["pass_rate"] * 100, 1)}
        for r in reversed(runs)
    ]
    st.line_chart(
        data={row["Run"]: row["Pass rate (%)"] for row in chart_data},
        use_container_width=True,
        height=220,
    )
elif len(runs) == 1:
    st.info("Only one run saved — run more evals to see the trend.")
else:
    st.info("No eval runs saved yet. Click **Run offline evals** below to start.")

# ── Run button ────────────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Run offline evals")

col_run, col_note = st.columns([1, 3])
with col_run:
    run_button = st.button("▶ Run now (offline)", use_container_width=True, type="primary")
with col_note:
    st.caption(
        "Replays all 10 golden trajectories through in-memory mock tools.  \n"
        "No AWS credentials or LLM required. Typically completes in < 1 second."
    )

if run_button:
    with st.spinner("Running eval suite…"):
        result = subprocess.run(
            [sys.executable, str(_RUNNER), "--results-dir", str(_RESULTS_DIR)],
            capture_output=True,
            text=True,
        )
    if result.returncode == 0:
        st.success("Eval run complete — all tests passed.")
    else:
        st.error("Eval run finished with failures.")
    with st.expander("Runner output"):
        st.code(result.stdout + result.stderr)
    st.cache_data.clear()
    st.rerun()

# ── Latest run detail ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Latest run — per-test results")

if not runs:
    st.info("No results yet.")
else:
    latest = runs[0]
    st.caption(f"Run at {fmt_ts(latest['run_at'])}  ·  Suite: `{latest.get('suite', 'offline_trajectory')}`")

    for res in latest["results"]:
        passed = res["passed"]
        header = f"{badge(passed)}  **{res['id']}** — {res['description']}"

        with st.expander(header, expanded=not passed):
            c1, c2 = st.columns([2, 1])

            with c1:
                st.markdown("**Trajectory**")
                traj = res.get("trajectory", [])
                if traj:
                    steps = "  →  ".join(f"`{t}`" for t in traj)
                    st.markdown(steps)
                else:
                    st.markdown("*(no tool calls)*")

            with c2:
                st.markdown(f"**Time:** `{res.get('elapsed_ms', '?')} ms`")

            st.markdown("**Rule checks**")
            for rule in res["rule_results"]:
                icon = rule_icon(rule["passed"])
                color = "green" if rule["passed"] else "red"
                st.markdown(
                    f":{color}[{icon}] `{rule['rule']}` · `{rule['detail']}` — {rule['message']}"
                )

# ── Run history table ─────────────────────────────────────────────────────────
if len(runs) > 1:
    st.markdown("---")
    st.subheader("Run history")

    rows = [
        {
            "Run at (UTC)":  fmt_ts(r["run_at"]),
            "Pass rate":     f"{r['pass_rate']*100:.1f}%",
            "Passed":        r["passed"],
            "Failed":        r["failed"],
            "Total":         r["total"],
            "Suite":         r.get("suite", "offline_trajectory"),
        }
        for r in runs
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

# ── Dataset overview ──────────────────────────────────────────────────────────
st.markdown("---")
with st.expander("📋 Eval dataset — all 10 golden examples"):
    dataset = load_dataset()
    if dataset:
        for ex in dataset:
            rules_summary = (
                f"{len(ex['rules']['must_call'])} must-call · "
                f"{len(ex['rules']['must_not_call'])} must-not-call · "
                f"{len(ex['rules']['order_before'])} ordering"
            )
            st.markdown(
                f"**{ex['id']}** &nbsp; {ex['description']}  \n"
                f"<small>Rules: {rules_summary}</small>",
                unsafe_allow_html=True,
            )
    else:
        st.info("Dataset file not found.")

# ── Eval workflow diagram ─────────────────────────────────────────────────────
st.markdown("---")
with st.expander("🗺 Complete eval workflow"):
    st.markdown("""
```
Developer changes a prompt or model
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  SMOKE SUITE  (every PR — < 30 seconds, no AWS needed)      │
│                                                             │
│  evals/run_evals.py                                         │
│    ├── Replay 10 golden trajectories through mock tools     │
│    ├── Check 31 trajectory rules (must_call / order_before) │
│    └── Save results to evals/results/run_<ts>.json          │
│                                                             │
│  ✅ All pass → PR can merge                                 │
│  ❌ Any fail → block merge, show failing rule here          │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ (nightly / on release)
┌─────────────────────────────────────────────────────────────┐
│  LIVE INTEGRATION SUITE  (nightly — requires AWS Bedrock)   │
│                                                             │
│  evals/test_live.py  (pytest)                               │
│    ├── Strands Agent + mock tools + real Bedrock LLM        │
│    ├── Rule-based trajectory checks (same rules as smoke)   │
│    └── DeepEval: TaskCompletionMetric + GEval groundedness  │
│         ├── Judge model: claude-opus-5-5                    │
│         └── Threshold: 0.7 on each metric                   │
│                                                             │
│  ✅ Pass → update baseline, tag release                     │
│  ❌ Fail → alert, block release                             │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ (production)
┌─────────────────────────────────────────────────────────────┐
│  ONLINE EVALS  (continuous — sample of live traffic)        │
│                                                             │
│  Langfuse: traces every production agent invocation         │
│    ├── Same OpenTelemetry schema → offline evals reuse      │
│    └── Tag traces with session_id, actor_id, model version  │
│                                                             │
│  DeepEval online monitors: rule-based checks run on         │
│  sampled production traces automatically                    │
│                                                             │
│  AgentCore onlineEvalConfigs: native AWS eval pipeline      │
│  (add evaluator entries to agentcore.json when ready)       │
└─────────────────────────────────────────────────────────────┘
```
""")

    st.markdown("""
**Missing pieces to wire up the full workflow:**

| Item | Status | How to complete |
|------|--------|-----------------|
| AWS credentials | Check sidebar 🔑 | Set env vars or configure `~/.aws` |
| Gateway OAuth secret | Check sidebar 🔑 | Move from `agentcore.json` to `.env` |
| DeepEval API key | Optional | Sign up at `app.confident-ai.com` |
| GitHub Actions OIDC role | CI only | Create IAM role, add `AWS_EVAL_ROLE_ARN` secret |
| Langfuse tracing | Optional | Self-host or use cloud, add keys to `.env` |
| AgentCore evaluators | Optional | Add entries to `agentcore.json` `evaluators[]` |
""")
