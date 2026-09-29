"""DiscoveryLab AI — Streamlit UI"""
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import streamlit as st
import json
from datetime import datetime

from src.agents.literature_agent import LiteratureAgent
from src.agents.hypothesis_agent import HypothesisAgent
from src.agents.critic_agent import CriticAgent
from src.agents.report_agent import ReportAgent


# ─────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DiscoveryLab AI",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4F46E5, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
    }
    .sub-header {
        color: #6B7280;
        font-size: 1.1rem;
        margin-top: -0.5rem;
        margin-bottom: 1.5rem;
    }
    .agent-box {
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #4F46E5;
        background: #F3F4F6;
        margin-bottom: 0.5rem;
    }
    .verdict-accept {
        color: #059669;
        font-weight: 700;
    }
    .verdict-needs {
        color: #D97706;
        font-weight: 700;
    }
    .verdict-reject {
        color: #DC2626;
        font-weight: 700;
    }
    .confidence-bar {
        height: 8px;
        border-radius: 4px;
        background: #E5E7EB;
        overflow: hidden;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────
st.markdown('<h1 class="main-header">🧬 DiscoveryLab AI</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Multi-agent scientific discovery system with adversarial critic</p>',
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    max_papers = st.slider("Max papers", 3, 15, 5)
    n_hypotheses = st.slider("Max hypotheses", 1, 10, 3)
    model = st.selectbox(
        "LLM Model",
        ["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
        index=0,
    )

    st.markdown("---")
    st.markdown("### 🤖 Agents")
    st.markdown("""
    - **📚 Literature** — finds papers (Crossref)
    - **💡 Hypothesis** — generates testable claims
    - **🔍 Critic** — tries to disprove them ⭐
    - **📄 Report** — writes research report
    """)

    st.markdown("---")
    st.caption("v0.1.0 • Built with LangGraph-style pipeline")


# ─────────────────────────────────────────────────────────
# MAIN INPUT
# ─────────────────────────────────────────────────────────
col1, col2 = st.columns([4, 1])

with col1:
    question = st.text_input(
        "🔬 Research Question",
        value="How can machine learning accelerate drug discovery?",
        placeholder="e.g., Find potential new drug candidates for target X",
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    run_button = st.button("🚀 Run Pipeline", use_container_width=True, type="primary")


# ─────────────────────────────────────────────────────────
# PIPELINE EXECUTION
# ─────────────────────────────────────────────────────────
if run_button and question.strip():
    st.markdown("---")
    st.markdown("### 📊 Pipeline Progress")

    # Progress trackers
    progress_bar = st.progress(0)
    status = st.empty()

    # Session state to hold results
    if "results" not in st.session_state:
        st.session_state.results = {}

    results = {}

    # ─── STEP 1: Literature ───
    with st.spinner("📚 Literature Agent searching..."):
        status.info("📚 Step 1/4: Literature Agent — searching papers...")
        lit_agent = LiteratureAgent(max_results=max_papers)
        lit_result = lit_agent.run(question)
        progress_bar.progress(25)

    if not lit_result["success"]:
        st.error("❌ Literature Agent failed. Try a different question.")
        st.stop()

    results["papers"] = lit_result["papers"]
    st.success(f"✅ Literature Agent: {lit_result['count']} papers found")

    # ─── STEP 2: Hypothesis ───
    with st.spinner("💡 Hypothesis Agent generating..."):
        status.info("💡 Step 2/4: Hypothesis Agent — generating testable hypotheses...")
        hyp_agent = HypothesisAgent(model=model, n_hypotheses=n_hypotheses)
        hyp_result = hyp_agent.run(question, lit_result["papers"])
        progress_bar.progress(50)

    if not hyp_result["success"]:
        st.error("❌ Hypothesis Agent failed.")
        st.stop()

    results["hypotheses"] = hyp_result["hypotheses"]
    st.success(f"✅ Hypothesis Agent: {hyp_result['count']} hypotheses generated")

    # ─── STEP 3: Critic ───
    with st.spinner("🔍 Critic Agent adversarially evaluating..."):
        status.info("🔍 Step 3/4: Critic Agent — trying to disprove hypotheses...")
        critic_agent = CriticAgent(model=model)
        critic_result = critic_agent.run(
            hyp_result["hypotheses"],
            lit_result["papers"],
            question,
        )
        progress_bar.progress(75)

    if not critic_result["success"]:
        st.error("❌ Critic Agent failed.")
        st.stop()

    results["critiques"] = critic_result["critiques"]
    st.success(f"✅ Critic Agent: {critic_result['count']} hypotheses evaluated")

    # ─── STEP 4: Report ───
    with st.spinner("📄 Report Agent writing report..."):
        status.info("📄 Step 4/4: Report Agent — synthesizing research report...")
        report_agent = ReportAgent(model=model)
        report_result = report_agent.run(
            question,
            lit_result["papers"],
            hyp_result["hypotheses"],
            critic_result["critiques"],
        )
        progress_bar.progress(100)

    if not report_result["success"]:
        st.error("❌ Report Agent failed.")
        st.stop()

    results["report"] = report_result["report"]
    results["question"] = question
    status.success("✅ Pipeline complete!")
    st.session_state.results = results


# ─────────────────────────────────────────────────────────
# DISPLAY RESULTS
# ─────────────────────────────────────────────────────────
if st.session_state.get("results"):
    r = st.session_state.results
    st.markdown("---")

    tabs = st.tabs(["📚 Papers", "💡 Hypotheses", "🔍 Critiques", "📄 Report"])

    # ─── TAB 1: PAPERS ───
    with tabs[0]:
        st.markdown(f"### 📚 {len(r['papers'])} Papers Reviewed")
        for i, p in enumerate(r["papers"], 1):
            with st.expander(f"[{i}] {p.get('title', 'Untitled')[:100]}"):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"**Authors:** {', '.join(p.get('authors', [])) or 'Unknown'}")
                    st.markdown(f"**Year:** {p.get('published') or 'n.d.'}")
                    st.markdown(f"**Source:** {p.get('source', '?')}")
                with col_b:
                    st.markdown(f"**Citations:** {p.get('citation_count', 0)}")
                    if p.get("url"):
                        st.markdown(f"**URL:** [{p['url'][:40]}...]({p['url']})")
                if p.get("abstract"):
                    st.markdown("**Abstract:**")
                    st.caption(p["abstract"][:500] + "...")

    # ─── TAB 2: HYPOTHESES ───
    with tabs[1]:
        st.markdown(f"### 💡 {len(r['hypotheses'])} Hypotheses Generated")
        for h in r["hypotheses"]:
            st.markdown(f"#### {h.get('id', '?')}")
            st.markdown(f"**Statement:** {h.get('statement', '')}")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Rationale:** {h.get('rationale', '')[:300]}")
                st.markdown(f"**Testability:** {h.get('testability', '')[:200]}")
            with col2:
                impact = h.get("expected_impact", "?")
                color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(impact.lower(), "⚪")
                st.markdown(f"**Impact:** {color} {impact.upper()}")
                st.markdown(f"**Evidence:** papers {h.get('evidence_sources', [])}")
            st.markdown("---")

    # ─── TAB 3: CRITIQUES ───
    with tabs[2]:
        st.markdown(f"### 🔍 Critic Evaluations")
        for c in r["critiques"]:
            h_id = c.get("hypothesis_id", "?")
            conf = c.get("confidence", 0)
            verdict = c.get("verdict", "?")

            verdict_class = {
                "ACCEPT": "verdict-accept",
                "NEEDS_EXPERIMENT": "verdict-needs",
                "REJECT": "verdict-reject",
            }.get(verdict, "")

            st.markdown(f"#### {h_id}")
            st.markdown(
                f'<span class="{verdict_class}">{verdict}</span> — '
                f'Confidence: **{conf:.2f}**',
                unsafe_allow_html=True,
            )
            st.progress(float(conf))

            if c.get("critic_summary"):
                st.info(c["critic_summary"][:500])

            col1, col2 = st.columns(2)
            with col1:
                if c.get("weaknesses"):
                    st.markdown("**⚠️ Weaknesses:**")
                    for w in c["weaknesses"]:
                        st.markdown(f"- {w}")
                if c.get("counter_evidence"):
                    st.markdown("**🚫 Counter-evidence:**")
                    for e in c["counter_evidence"]:
                        st.markdown(f"- {e}")
            with col2:
                if c.get("alternative_explanations"):
                    st.markdown("**🔄 Alternatives:**")
                    for a in c["alternative_explanations"]:
                        st.markdown(f"- {a}")
                if c.get("required_experiments"):
                    st.markdown("**🧪 Required experiments:**")
                    for e in c["required_experiments"]:
                        st.markdown(f"- {e}")
            st.markdown("---")

    # ─── TAB 4: REPORT ───
    with tabs[3]:
        st.markdown("### 📄 Final Research Report")
        st.markdown(r["report"])

        # Download button
        safe_name = "".join(c if c.isalnum() else "_" for c in r["question"])[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 Download Report (Markdown)",
            data=r["report"],
            file_name=f"{safe_name}_{timestamp}.md",
            mime="text/markdown",
        )

        st.download_button(
            label="📥 Download Full Data (JSON)",
            data=json.dumps(r, indent=2, ensure_ascii=False),
            file_name=f"{safe_name}_{timestamp}.json",
            mime="application/json",
        )

else:
    # Landing state
    st.markdown("---")
    st.markdown("### 🎯 How It Works")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("#### 📚 Literature")
        st.caption("Searches academic papers via Crossref, OpenAlex, Semantic Scholar")
    with col2:
        st.markdown("#### 💡 Hypothesis")
        st.caption("Generates testable, evidence-backed hypotheses from papers")
    with col3:
        st.markdown("#### 🔍 Critic")
        st.caption("Adversarially challenges each hypothesis. Finds counter-evidence.")
    with col4:
        st.markdown("#### 📄 Report")
        st.caption("Synthesizes everything into a research-grade report")

    st.markdown("---")
    st.info("👆 Enter a research question above and click **Run Pipeline** to start.")