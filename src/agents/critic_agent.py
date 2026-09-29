"""Critic Agent — adversarially challenges hypotheses to find weaknesses"""
import json
import logging
from pathlib import Path
from typing import List, Dict
from rich.console import Console

from src.core.llm_client import get_llm, safe_json_invoke

console = Console()
logger = logging.getLogger(__name__)


CRITIC_PROMPT = """You are an adversarial Critic Agent in a scientific discovery system.

Your job: TRY TO DISPROVE the given hypothesis. Be skeptical, rigorous, and adversarial.

HYPOTHESIS:
{h}

RESEARCH QUESTION:
{question}

SUPPORTING PAPERS:
{papers}

Analyze the hypothesis critically:

1. **Weaknesses**: What could be wrong? Hidden assumptions? Confounders?
2. **Counter-evidence**: What evidence contradicts or weakens this?
3. **Alternative explanations**: What else could explain the same outcome?
4. **Missing controls**: What experiments are needed to rule out alternatives?
5. **Scope limitations**: Where would this NOT apply?

Return ONLY valid JSON:
{{
  "confidence": 0.75,
  "verdict": "ACCEPT | NEEDS_EXPERIMENT | REJECT",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "counter_evidence": ["counter-evidence 1"],
  "alternative_explanations": ["alternative 1"],
  "missing_controls": ["control 1", "control 2"],
  "scope_limitations": ["limitation 1"],
  "required_experiments": ["experiment 1"],
  "critic_summary": "One paragraph summary of the critique"
}}

Rules:
- confidence 0.0-1.0 (how likely hypothesis is true after critique)
- verdict: ACCEPT (conf>0.8) | NEEDS_EXPERIMENT (0.5-0.8) | REJECT (<0.5)
- Be SPECIFIC, not generic
- Reference paper numbers when relevant
- Start with {{ and end with }}
"""


class CriticAgent:
    """Adversarially challenges hypotheses"""

    def __init__(
        self,
        model: str = "openai/gpt-oss-120b",
        output_dir: str = "./data/evidence",
    ):
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = get_llm(model=model, temperature=0.4, json_mode=True)
        console.print(f"[cyan]Critic Agent initialized (model: {model})[/cyan]")

    def _format_papers(self, papers: List[Dict], max_papers: int = 10) -> str:
        """Format papers with numbered refs"""
        lines = []
        for i, p in enumerate(papers[:max_papers], 1):
            title = p.get("title", "")[:120]
            abstract = (p.get("abstract") or "")[:400]
            lines.append(f"[{i}] {title}")
            if abstract:
                lines.append(f"    {abstract}...")
            lines.append("")
        return "\n".join(lines)

    def critique(
        self,
        hypothesis: Dict,
        papers: List[Dict],
        question: str,
    ) -> Dict:
        """Critique a single hypothesis"""
        h_id = hypothesis.get("id", "?")
        statement = hypothesis.get("statement", "")

        console.print(f"\n   [cyan]Critiquing {h_id}...[/cyan]")

        papers_text = self._format_papers(papers)

        # Format hypothesis for prompt
        h_text = json.dumps(hypothesis, indent=2)

        prompt = CRITIC_PROMPT.format(
            h=h_text,
            question=question,
            papers=papers_text,
        )

        try:
            result = safe_json_invoke(self.llm, prompt)

            # Ensure required fields
            result.setdefault("confidence", 0.5)
            result.setdefault("verdict", "NEEDS_EXPERIMENT")
            result.setdefault("strengths", [])
            result.setdefault("weaknesses", [])
            result.setdefault("counter_evidence", [])
            result.setdefault("alternative_explanations", [])
            result.setdefault("missing_controls", [])
            result.setdefault("scope_limitations", [])
            result.setdefault("required_experiments", [])
            result.setdefault("critic_summary", "")

            # Add hypothesis info
            result["hypothesis_id"] = h_id
            result["hypothesis_statement"] = statement

            confidence = result["confidence"]
            verdict = result["verdict"]

            color = "green" if verdict == "ACCEPT" else "yellow" if verdict == "NEEDS_EXPERIMENT" else "red"
            console.print(
                f"   [{color}]{h_id}: {verdict} (confidence: {confidence:.2f})[/{color}]"
            )

            return result

        except Exception as e:
            logger.error(f"Critique failed for {h_id}: {e}")
            console.print(f"   [red]Failed: {e}[/red]")
            return {
                "hypothesis_id": h_id,
                "confidence": 0.0,
                "verdict": "REJECT",
                "error": str(e),
            }

    def critique_all(
        self,
        hypotheses: List[Dict],
        papers: List[Dict],
        question: str,
    ) -> List[Dict]:
        """Critique all hypotheses"""
        console.print(f"\n[bold cyan]CRITIC AGENT[/bold cyan]")
        console.print(f"   Hypotheses: {len(hypotheses)}")
        console.print(f"   Papers: {len(papers)}")

        critiques = []
        for h in hypotheses:
            critique = self.critique(h, papers, question)
            critiques.append(critique)

        # Sort by confidence (highest first)
        critiques.sort(key=lambda c: c.get("confidence", 0), reverse=True)

        return critiques

    def save(self, critiques: List[Dict], question: str) -> str:
        """Save critiques to JSON"""
        safe_name = "".join(c if c.isalnum() else "_" for c in question)[:50]
        file = self.output_dir / f"{safe_name}_critiques.json"
        file.write_text(
            json.dumps(critiques, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(f"\n   [green]💾 Saved: {file}[/green]")
        return str(file)

    def run(
        self,
        hypotheses: List[Dict],
        papers: List[Dict],
        question: str,
    ) -> Dict:
        """Full critic run"""
        critiques = self.critique_all(hypotheses, papers, question)

        if not critiques:
            return {"success": False, "critiques": [], "file": None}

        file = self.save(critiques, question)

        return {
            "success": True,
            "critiques": critiques,
            "file": file,
            "count": len(critiques),
        }


def display_critiques(critiques: List[Dict]):
    """Pretty-print critiques"""
    console.print("\n" + "="*70)
    console.print("[bold]CRITIC REPORTS[/bold]")
    console.print("="*70 + "\n")

    for c in critiques:
        h_id = c.get("hypothesis_id", "?")
        conf = c.get("confidence", 0)
        verdict = c.get("verdict", "?")

        color = "green" if verdict == "ACCEPT" else "yellow" if verdict == "NEEDS_EXPERIMENT" else "red"

        console.print(f"[bold cyan]{h_id}[/bold cyan] — [{color}]{verdict}[/{color}] (confidence: {conf:.2f})")
        console.print(f"  [dim]{c.get('critic_summary', '')[:300]}[/dim]\n")

        if c.get("weaknesses"):
            console.print(f"  [red]Weaknesses:[/red]")
            for w in c["weaknesses"][:3]:
                console.print(f"    • {w}")

        if c.get("counter_evidence"):
            console.print(f"  [red]Counter-evidence:[/red]")
            for e in c["counter_evidence"][:3]:
                console.print(f"    • {e}")

        if c.get("required_experiments"):
            console.print(f"  [yellow]Required experiments:[/yellow]")
            for e in c["required_experiments"][:3]:
                console.print(f"    • {e}")

        console.print()


if __name__ == "__main__":
    from src.agents.literature_agent import LiteratureAgent
    from src.agents.hypothesis_agent import HypothesisAgent

    console.print("\n" + "="*70)
    console.print("[bold magenta]Critic Agent Test — Full Pipeline[/bold magenta]")
    console.print("="*70)

    # Full pipeline
    question = "How can machine learning accelerate drug discovery?"

    # 1. Literature
    lit = LiteratureAgent(max_results=5)
    lit_result = lit.run(question)

    if not lit_result["success"]:
        console.print("[red]Literature failed[/red]")
        exit(1)

    # 2. Hypothesis
    hyp = HypothesisAgent(n_hypotheses=3)
    hyp_result = hyp.run(question, lit_result["papers"])

    if not hyp_result["success"]:
        console.print("[red]Hypothesis failed[/red]")
        exit(1)

    # 3. Critic — KILLER FEATURE
    critic = CriticAgent()
    critic_result = critic.run(
        hyp_result["hypotheses"],
        lit_result["papers"],
        question,
    )

    # 4. Display
    if critic_result["success"]:
        display_critiques(critic_result["critiques"])