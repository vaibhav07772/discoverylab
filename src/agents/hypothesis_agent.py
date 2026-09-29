"""Hypothesis Agent — generates testable hypotheses from literature"""
import json
import logging
from pathlib import Path
from typing import List, Dict
from rich.console import Console
from rich.table import Table

from src.core.llm_client import get_llm, safe_json_invoke

console = Console()
logger = logging.getLogger(__name__)


HYPOTHESIS_PROMPT = """You are a Hypothesis Agent in a scientific discovery system.

Given a research question and relevant papers, generate {n} novel, testable hypotheses.

RESEARCH QUESTION:
{question}

RELEVANT PAPERS (with abstracts):
{papers}

Generate {n} hypotheses that:
1. Address the research question
2. Are specific and testable (not vague)
3. Are grounded in the provided literature
4. Can be tested computationally or experimentally
5. Propose something NEW (not just summarizing existing work)

Return ONLY valid JSON:
{{
  "hypotheses": [
    {{
      "id": "H-001",
      "statement": "Clear, specific, testable hypothesis (1-2 sentences)",
      "rationale": "Why this might be true based on the literature",
      "evidence_sources": [1, 3, 5],
      "testability": "How this could be tested (method/dataset/metric)",
      "novelty": "What's new compared to existing work",
      "expected_impact": "low | medium | high"
    }}
  ]
}}

Start with {{ and end with }}."""


class HypothesisAgent:
    """Generates testable hypotheses from literature"""

    def __init__(
        self,
        model: str = "openai/gpt-oss-120b",
        n_hypotheses: int = 5,
        output_dir: str = "./data/hypotheses",
    ):
        self.model = model
        self.n_hypotheses = n_hypotheses
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = get_llm(model=model, temperature=0.7, json_mode=True)
        console.print(f"[cyan]Hypothesis Agent initialized (model: {model})[/cyan]")

    def _format_papers(self, papers: List[Dict], max_papers: int = 10) -> str:
        """Format papers for prompt (with numbered references)"""
        lines = []
        for i, p in enumerate(papers[:max_papers], 1):
            title = p.get("title", "")[:150]
            authors = ", ".join(p.get("authors", [])[:3]) or "Unknown"
            year = p.get("published", "") or "n.d."
            abstract = (p.get("abstract") or "")[:600]

            lines.append(f"[{i}] {title}")
            lines.append(f"    Authors: {authors} ({year})")
            if abstract:
                lines.append(f"    Abstract: {abstract}...")
            lines.append("")

        return "\n".join(lines)

    def generate(self, question: str, papers: List[Dict]) -> List[Dict]:
        """Generate hypotheses from papers"""
        console.print(f"\n[bold cyan]HYPOTHESIS AGENT[/bold cyan]")
        console.print(f"   Question: {question[:80]}")
        console.print(f"   Papers: {len(papers)}")

        if not papers:
            console.print("   [red]❌ No papers provided[/red]")
            return []

        papers_text = self._format_papers(papers)

        prompt = HYPOTHESIS_PROMPT.format(
            question=question,
            papers=papers_text,
            n=self.n_hypotheses,
        )

        try:
            console.print(f"   [dim]Generating {self.n_hypotheses} hypotheses...[/dim]")
            result = safe_json_invoke(self.llm, prompt)
            hypotheses = result.get("hypotheses", [])

            console.print(f"   [green]✅ Generated {len(hypotheses)} hypotheses[/green]")
            return hypotheses

        except Exception as e:
            logger.error(f"Hypothesis generation failed: {e}")
            console.print(f"   [red]❌ Failed: {e}[/red]")
            return []

    def save(self, hypotheses: List[Dict], question: str) -> str:
        """Save hypotheses to JSON"""
        safe_name = "".join(c if c.isalnum() else "_" for c in question)[:50]
        file = self.output_dir / f"{safe_name}.json"
        file.write_text(
            json.dumps(hypotheses, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        console.print(f"   [green]💾 Saved: {file}[/green]")
        return str(file)

    def run(self, question: str, papers: List[Dict]) -> Dict:
        """Full agent run: generate + save"""
        hypotheses = self.generate(question, papers)

        if not hypotheses:
            return {"success": False, "hypotheses": [], "file": None}

        file = self.save(hypotheses, question)

        return {
            "success": True,
            "hypotheses": hypotheses,
            "file": file,
            "count": len(hypotheses),
        }


def display_hypotheses(hypotheses: List[Dict]):
    """Pretty-print hypotheses"""
    console.print(f"\n[bold]Generated Hypotheses:[/bold]\n")
    for h in hypotheses:
        console.print(f"[bold cyan]{h.get('id', '?')}[/bold cyan]")
        console.print(f"  [yellow]Statement:[/yellow] {h.get('statement', '')}")
        console.print(f"  [dim]Rationale:[/dim] {h.get('rationale', '')[:200]}")
        sources = h.get("evidence_sources", [])
        console.print(f"  [dim]Evidence:[/dim] papers {sources}")
        console.print(f"  [dim]Testability:[/dim] {h.get('testability', '')[:150]}")
        console.print(f"  [dim]Impact:[/dim] {h.get('expected_impact', '?')}")
        console.print()


if __name__ == "__main__":
    from src.agents.literature_agent import LiteratureAgent

    console.print("\n" + "="*70)
    console.print("[bold magenta]Hypothesis Agent Test[/bold magenta]")
    console.print("="*70)

    # Step 1: Get papers
    question = "How can machine learning accelerate drug discovery?"
    lit_agent = LiteratureAgent(max_results=5)
    lit_result = lit_agent.run(question)

    if not lit_result["success"]:
        console.print("[red]Literature search failed[/red]")
        exit(1)

    # Step 2: Generate hypotheses
    hyp_agent = HypothesisAgent(n_hypotheses=3)
    result = hyp_agent.run(question, lit_result["papers"])

    # Step 3: Display
    if result["success"]:
        display_hypotheses(result["hypotheses"])
    else:
        console.print("[red]Hypothesis generation failed[/red]")