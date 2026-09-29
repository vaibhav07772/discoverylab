"""Report Agent — generates final research report from all agents"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from rich.console import Console

from src.core.llm_client import get_llm, safe_invoke

console = Console()
logger = logging.getLogger(__name__)


REPORT_PROMPT = """You are a Report Agent in a scientific discovery system.

Write a comprehensive research report in Markdown based on the analysis below.

RESEARCH QUESTION:
{question}

LITERATURE REVIEWED ({n_papers} papers):
{papers}

HYPOTHESES GENERATED ({n_hypotheses}):
{hypotheses}

CRITIC EVALUATIONS:
{critiques}

Write a professional research report with these sections:

# Research Report: {question}

## Executive Summary
(3-4 sentences summarizing key findings, confidence levels, and recommendations)

## Research Question
(restate the question)

## Methodology
(describe the multi-agent pipeline: Literature → Hypothesis → Critic → Report)

## Literature Review
(summarize the papers reviewed, grouped by theme)

## Hypotheses & Evaluation
For each hypothesis, provide:
- **Hypothesis ID**: statement
- **Confidence**: X.XX
- **Verdict**: ACCEPT / NEEDS_EXPERIMENT / REJECT
- **Supporting Evidence**: (from papers)
- **Critic Analysis**: (key weaknesses + counter-evidence)
- **Required Experiments**: (what would validate/reject it)

## Recommendations
(Which hypotheses are worth pursuing? What experiments should be run first?)

## Limitations
(honest assessment of what this analysis cannot determine)

## References
(numbered list of all papers)

Rules:
- Be specific, cite paper numbers [1], [2], etc.
- Do NOT overstate confidence
- Highlight which hypotheses need experimental validation
- Keep it professional, research-grade
- Output ONLY the markdown report (no preamble, no code fences)
"""


class ReportAgent:
    """Generates final research report"""

    def __init__(
        self,
        model: str = "openai/gpt-oss-120b",
        output_dir: str = "./reports",
    ):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = get_llm(model=model, temperature=0.3)
        console.print(f"[cyan]Report Agent initialized (model: {model})[/cyan]")

    def _format_papers(self, papers: List[Dict]) -> str:
        lines = []
        for i, p in enumerate(papers, 1):
            title = p.get("title", "")[:150]
            authors = ", ".join(p.get("authors", [])[:3]) or "Unknown"
            year = p.get("published", "") or "n.d."
            venue = p.get("venue", "")
            lines.append(f"[{i}] {title}")
            lines.append(f"    {authors} ({year}) {venue}")
        return "\n".join(lines)

    def _format_hypotheses(self, hypotheses: List[Dict]) -> str:
        lines = []
        for h in hypotheses:
            lines.append(f"{h.get('id', '?')}: {h.get('statement', '')}")
            lines.append(f"    Rationale: {h.get('rationale', '')[:200]}")
            lines.append(f"    Testability: {h.get('testability', '')[:200]}")
            lines.append(f"    Expected Impact: {h.get('expected_impact', '?')}")
            lines.append("")
        return "\n".join(lines)

    def _format_critiques(self, critiques: List[Dict]) -> str:
        lines = []
        for c in critiques:
            h_id = c.get("hypothesis_id", "?")
            conf = c.get("confidence", 0)
            verdict = c.get("verdict", "?")
            lines.append(f"{h_id} — {verdict} (confidence: {conf:.2f})")
            if c.get("critic_summary"):
                lines.append(f"    Summary: {c['critic_summary'][:300]}")
            if c.get("weaknesses"):
                lines.append("    Weaknesses:")
                for w in c["weaknesses"][:3]:
                    lines.append(f"      - {w[:150]}")
            if c.get("counter_evidence"):
                lines.append("    Counter-evidence:")
                for e in c["counter_evidence"][:2]:
                    lines.append(f"      - {e[:150]}")
            if c.get("required_experiments"):
                lines.append("    Required experiments:")
                for e in c["required_experiments"][:2]:
                    lines.append(f"      - {e[:150]}")
            lines.append("")
        return "\n".join(lines)

    def generate(
        self,
        question: str,
        papers: List[Dict],
        hypotheses: List[Dict],
        critiques: List[Dict],
    ) -> str:
        """Generate markdown report"""
        console.print(f"\n[bold cyan]REPORT AGENT[/bold cyan]")
        console.print(f"   Papers: {len(papers)}")
        console.print(f"   Hypotheses: {len(hypotheses)}")
        console.print(f"   Critiques: {len(critiques)}")

        prompt = REPORT_PROMPT.format(
            question=question,
            n_papers=len(papers),
            n_hypotheses=len(hypotheses),
            papers=self._format_papers(papers),
            hypotheses=self._format_hypotheses(hypotheses),
            critiques=self._format_critiques(critiques),
        )

        try:
            console.print("   [dim]Writing report...[/dim]")
            response = safe_invoke(self.llm, prompt)
            report = response.content.strip()

            # Strip code fences if present
            if report.startswith("```"):
                report = report.split("```")[1]
                if report.startswith("markdown") or report.startswith("md"):
                    report = report.split("\n", 1)[1]
                report = report.strip()

            console.print(f"   [green]✅ Report generated ({len(report)} chars)[/green]")
            return report

        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            console.print(f"   [red]❌ Failed: {e}[/red]")
            return ""

    def save(self, report: str, question: str) -> Dict:
        """Save report as .md + .json"""
        safe_name = "".join(c if c.isalnum() else "_" for c in question)[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        md_file = self.output_dir / f"{safe_name}_{timestamp}.md"
        md_file.write_text(report, encoding="utf-8")

        console.print(f"   [green]💾 Saved: {md_file}[/green]")
        return {"markdown": str(md_file)}

    def run(
        self,
        question: str,
        papers: List[Dict],
        hypotheses: List[Dict],
        critiques: List[Dict],
    ) -> Dict:
        """Full report run"""
        report = self.generate(question, papers, hypotheses, critiques)

        if not report:
            return {"success": False, "report": "", "file": None}

        files = self.save(report, question)

        return {
            "success": True,
            "report": report,
            "file": files["markdown"],
            "length": len(report),
        }


def display_report_preview(report: str, lines: int = 40):
    """Show first N lines of report"""
    console.print("\n" + "="*70)
    console.print("[bold]REPORT PREVIEW[/bold]")
    console.print("="*70 + "\n")
    for line in report.split("\n")[:lines]:
        console.print(line)
    console.print("\n[dim]... (truncated)[/dim]")


if __name__ == "__main__":
    from src.agents.literature_agent import LiteratureAgent
    from src.agents.hypothesis_agent import HypothesisAgent
    from src.agents.critic_agent import CriticAgent

    console.print("\n" + "="*70)
    console.print("[bold magenta]Report Agent Test — Full Pipeline[/bold magenta]")
    console.print("="*70)

    question = "How can machine learning accelerate drug discovery?"

    # 1. Literature
    lit_result = LiteratureAgent(max_results=5).run(question)
    if not lit_result["success"]:
        console.print("[red]Literature failed[/red]")
        exit(1)

    # 2. Hypothesis
    hyp_result = HypothesisAgent(n_hypotheses=3).run(question, lit_result["papers"])
    if not hyp_result["success"]:
        console.print("[red]Hypothesis failed[/red]")
        exit(1)

    # 3. Critic
    critic_result = CriticAgent().run(
        hyp_result["hypotheses"], lit_result["papers"], question
    )
    if not critic_result["success"]:
        console.print("[red]Critic failed[/red]")
        exit(1)

    # 4. Report — FINAL STEP
    report_agent = ReportAgent()
    report_result = report_agent.run(
        question,
        lit_result["papers"],
        hyp_result["hypotheses"],
        critic_result["critiques"],
    )

    if report_result["success"]:
        display_report_preview(report_result["report"])
        console.print(f"\n[bold green]📄 Full report: {report_result['file']}[/bold green]")
    else:
        console.print("[red]Report generation failed[/red]")