from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.auth import require_password
from src.auditor import analyze_presentation
from src.llm_judge import run_llm_judge, semantic_findings_to_issues

st.set_page_config(page_title="Enterprise Document Brand Auditor", page_icon="📊", layout="wide")

if not require_password():
    st.stop()

st.title("Enterprise Document Brand Auditor")
st.caption("Upload a PowerPoint deck, review Enterprise brand-compliance issues by slide, and accept/reject flags.")
with st.sidebar:
    st.header("Review settings")
    include_notes = st.checkbox(
        "Show annotated-deck notes",
        value=False,
        help="Use this only when evaluating against the annotated training deck. Turn off for production-like review.",
    )

    sensitivity_label = st.selectbox(
        "Review sensitivity",
        [
            "Conservative - high only",
            "Balanced - medium and high",
            "Detailed - all findings",
        ],
        index=0,
        help="Conservative reduces noise for executive review. Balanced shows stronger QA findings. Detailed includes all rule-based review items.",
    )

    min_severity = {
        "Conservative - high only": "high",
        "Balanced - medium and high": "medium",
        "Detailed - all findings": "low",
    }[sensitivity_label]

    severity_rank = {"low": 0, "medium": 1, "high": 2}

    st.markdown("---")
    enable_ai_judge = st.checkbox(
        "Enable AI-assisted judge",
        value=False,
        help="Optional second-pass LLM review. Deterministic rules remain the source of truth; AI output is advisory and must be human-confirmed.",
    )
    ai_provider = "OpenAI"
    ai_model = "gpt-4o-mini"
    ai_max_issues = 25
    if enable_ai_judge:
        ai_provider = st.selectbox("AI provider", ["Gemini", "OpenAI", "Groq"], index=0)
        default_model = {
            "Gemini": "gemini-2.5-flash",
            "OpenAI": "gpt-4o-mini",
            "Groq": "llama-3.1-8b-instant",
        }[ai_provider]
        ai_model = st.text_input("AI model", value=default_model)
        ai_max_issues = st.slider("Max deterministic flags for AI judge", min_value=5, max_value=50, value=25, step=5)
        st.caption("Configure GEMINI_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY in Streamlit secrets. The AI judge verifies and prioritizes findings; it does not auto-accept flags.")

    st.markdown("---")
    st.write("Default demo password is `enterprise-demo-2026` unless APP_PASSWORD is set.")
    
uploaded = st.file_uploader("Upload Enterprise PPTX", type=["pptx"])

if not uploaded:
    st.info("Upload a PowerPoint deck to begin.")
    st.stop()

with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
    tmp.write(uploaded.getbuffer())
    pptx_path = Path(tmp.name)

with st.spinner("Analyzing PowerPoint..."):
    report = analyze_presentation(pptx_path, include_annotated_notes=include_notes)

if "review_status" not in st.session_state:
    st.session_state.review_status = {}

all_issues = report.issues
visible_issues = [i for i in all_issues if severity_rank[i.severity] >= severity_rank[min_severity]]

ai_judge_result = None
ai_semantic_issues = []
if enable_ai_judge and visible_issues:
    with st.spinner("Running optional AI judge..."):
        ai_judge_result = run_llm_judge(report, visible_issues, provider=ai_provider, model=ai_model, max_issues=ai_max_issues)
        if ai_judge_result.available:
            ai_semantic_issues = semantic_findings_to_issues(ai_judge_result.semantic_findings)
            all_issues = all_issues + ai_semantic_issues
            visible_issues = [i for i in all_issues if severity_rank[i.severity] >= severity_rank[min_severity]]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Slides", report.slide_count)
col2.metric("Visible issues", len(visible_issues))
col3.metric("High severity", sum(1 for i in visible_issues if i.severity == "high"))
col4.metric("Annotated notes found", report.annotated_notes_found)

st.markdown("---")

if ai_judge_result is not None:
    with st.expander("AI-assisted judge summary", expanded=True):
        if ai_judge_result.available:
            st.success(f"AI judge ran with {ai_judge_result.provider} / {ai_judge_result.model} on {ai_judge_result.reviewed_issue_count} deterministic findings.")
        else:
            st.warning(ai_judge_result.summary)
            if ai_judge_result.error:
                st.caption(f"AI config/status: {ai_judge_result.error}")
        st.write(ai_judge_result.summary)
        if ai_judge_result.high_priority_rule_ids:
            st.write("**Prioritize:**", ", ".join(ai_judge_result.high_priority_rule_ids))
        if ai_judge_result.possible_noise_rule_ids:
            st.write("**Potentially noisy / confirm manually:**", ", ".join(ai_judge_result.possible_noise_rule_ids))
        if ai_semantic_issues:
            st.caption("AI semantic findings are added as advisory review items with low confidence. They require human confirmation.")

slide_nums = [s.slide_number for s in report.slide_summaries]
selected_slide = st.selectbox("Select slide", slide_nums, format_func=lambda n: f"Slide {n}: {next((s.title for s in report.slide_summaries if s.slide_number == n), '')[:90]}")

slide_summary = next(s for s in report.slide_summaries if s.slide_number == selected_slide)
slide_issues = [i for i in visible_issues if i.slide_number == selected_slide]

left, right = st.columns([0.42, 0.58], gap="large")

with left:
    st.subheader(f"Slide {selected_slide}")
    st.write(slide_summary.title)
    st.write(f"Issues: {len(slide_issues)}")
    if slide_summary.notes and include_notes:
        with st.expander("Annotated notes extracted from slide"):
            for note in slide_summary.notes:
                st.write(f"- {note}")
    st.caption("Slide image overlay can be added in production using LibreOffice/PDF rendering. This case-study version prioritizes issue review and evidence.")

with right:
    st.subheader("Issues")
    if not slide_issues:
        st.success("No visible issues for this slide at the selected severity threshold.")
    for idx, issue in enumerate(slide_issues):
        key = f"{issue.slide_number}-{issue.rule_id}-{idx}-{issue.evidence[:20]}"
        current = st.session_state.review_status.get(key, issue.status)
        border = {"high": "🔴", "medium": "🟠", "low": "🔵"}[issue.severity]
        with st.container(border=True):
            st.markdown(f"**{border} {issue.title}**")
            st.caption(f"{issue.category} · {issue.severity.upper()} · confidence {issue.confidence:.0%} · rule `{issue.rule_id}`")
            st.write("**Evidence:**", issue.evidence)
            st.write("**Recommendation:**", issue.recommendation)
            if issue.bbox:
                st.caption(f"Shape: {issue.shape_name or 'unknown'} · Box: {issue.bbox}")
            new_status = st.radio("Reviewer decision", ["pending", "accepted", "rejected"], index=["pending", "accepted", "rejected"].index(current), key=key, horizontal=True)
            st.session_state.review_status[key] = new_status

st.markdown("---")
st.subheader("Export reviewed results")

rows = []
for idx, issue in enumerate(visible_issues):
    key_prefix = f"{issue.slide_number}-{issue.rule_id}-{idx}-{issue.evidence[:20]}"
    # Status keys are exact in the issue cards only for current slide; use pending fallback for export.
    status = "pending"
    for k, v in st.session_state.review_status.items():
        if k.startswith(f"{issue.slide_number}-{issue.rule_id}") and issue.evidence[:20] in k:
            status = v
            break
    d = issue.to_dict()
    d["status"] = status
    rows.append(d)

df = pd.DataFrame(rows)
if not df.empty:
    st.dataframe(df[["slide_number", "severity", "category", "title", "evidence", "recommendation", "confidence", "status"]], use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="enterprise_pptx_audit.csv", mime="text/csv")
    st.download_button("Download JSON", json.dumps(rows, indent=2).encode("utf-8"), file_name="enterprise_pptx_audit.json", mime="application/json")
else:
    st.info("No issues to export at the selected severity threshold.")
