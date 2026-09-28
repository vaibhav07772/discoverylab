"""Literature Agent — searches academic papers (Semantic Scholar + OpenAlex)"""
import requests
import json
import time
import logging
from pathlib import Path
from typing import List, Dict
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

# Free APIs (no key required)
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
OPENALEX_API = "https://api.openalex.org/works"

USER_AGENT = "DiscoveryLab/1.0 (mailto:vs9502778@gmail.com)"


class LiteratureAgent:
    """Searches academic papers via Semantic Scholar (primary) + OpenAlex (fallback)"""
    
    def __init__(self, max_results: int = 10, output_dir: str = "./data/papers"):
        self.max_results = max_results
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _search_semantic_scholar(self, query: str, n: int) -> List[Dict]:
        """Semantic Scholar API — free, no key required"""
        params = {
            "query": query,
            "limit": min(n, 20),
            "fields": "title,abstract,authors,year,venue,externalIds,url,citationCount",
        }
        headers = {"User-Agent": USER_AGENT}
        
        resp = requests.get(
            SEMANTIC_SCHOLAR_API,
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        papers = []
        for p in data.get("data", []):
            papers.append({
                "title": p.get("title", ""),
                "authors": [a.get("name", "") for a in (p.get("authors") or [])[:3]],
                "abstract": p.get("abstract") or "",
                "published": str(p.get("year") or ""),
                "url": p.get("url", ""),
                "venue": p.get("venue", ""),
                "citation_count": p.get("citationCount", 0),
                "external_ids": p.get("externalIds", {}),
                "source": "semantic_scholar",
            })
        return papers
    
    def _search_openalex(self, query: str, n: int) -> List[Dict]:
        """OpenAlex API — free, no key required, 250M+ papers"""
        params = {
            "search": query,
            "per-page": min(n, 25),
            "mailto": "vs9502778@gmail.com",
        }
        headers = {"User-Agent": USER_AGENT}
        
        resp = requests.get(
            OPENALEX_API,
            params=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        
        papers = []
        for p in data.get("results", []):
            authors = []
            for a in (p.get("authorships") or [])[:3]:
                author = a.get("author", {})
                if author.get("display_name"):
                    authors.append(author["display_name"])
            
            papers.append({
                "title": p.get("title", ""),
                "authors": authors,
                "abstract": self._reconstruct_abstract(p.get("abstract_inverted_index")),
                "published": str(p.get("publication_year") or ""),
                "url": p.get("id", ""),
                "doi": p.get("doi", ""),
                "citation_count": p.get("cited_by_count", 0),
                "source": "openalex",
            })
        return papers
    
    def _reconstruct_abstract(self, inverted_index) -> str:
        """OpenAlex stores abstracts as inverted index — reconstruct it"""
        if not inverted_index:
            return ""
        try:
            words = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    words.append((pos, word))
            words.sort()
            return " ".join(w for _, w in words)
        except Exception:
            return ""
    
    def search(self, query: str, max_results: int = None) -> List[Dict]:
        """Search papers: try Semantic Scholar, fall back to OpenAlex"""
        n = max_results or self.max_results
        
        console.print(f"\n[cyan]📚 Searching papers:[/cyan] {query}")
        console.print(f"   Max results: {n}")
        
        # Try Semantic Scholar first
        try:
            console.print("   [dim]Trying Semantic Scholar...[/dim]")
            papers = self._search_semantic_scholar(query, n)
            if papers:
                console.print(f"   [green]✅ Semantic Scholar: {len(papers)} papers[/green]")
                return papers
        except Exception as e:
            console.print(f"   [yellow]Semantic Scholar failed: {str(e)[:100]}[/yellow]")
        
        # Fallback to OpenAlex
        try:
            console.print("   [dim]Falling back to OpenAlex...[/dim]")
            time.sleep(1)
            papers = self._search_openalex(query, n)
            if papers:
                console.print(f"   [green]✅ OpenAlex: {len(papers)} papers[/green]")
                return papers
        except Exception as e:
            console.print(f"   [red]OpenAlex failed: {str(e)[:100]}[/red]")
        
        console.print("   [red]❌ All sources failed[/red]")
        return []
    
    def save_papers(self, papers: List[Dict], query: str) -> str:
        """Save papers to JSON"""
        safe_name = "".join(c if c.isalnum() else "_" for c in query)[:50]
        file = self.output_dir / f"{safe_name}.json"
        file.write_text(json.dumps(papers, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"   [green]💾 Saved: {file}[/green]")
        return str(file)
    
    def run(self, query: str) -> Dict:
        """Full agent run: search + save"""
        console.print(f"\n[bold cyan]LITERATURE AGENT[/bold cyan]")
        
        papers = self.search(query)
        
        if not papers:
            return {"success": False, "papers": [], "file": None, "count": 0}
        
        file = self.save_papers(papers, query)
        
        return {
            "success": True,
            "papers": papers,
            "file": file,
            "count": len(papers),
        }


if __name__ == "__main__":
    console.print("\n" + "="*70)
    console.print("[bold magenta]Literature Agent Test[/bold magenta]")
    console.print("="*70)
    
    agent = LiteratureAgent(max_results=5)
    
    result = agent.run("drug discovery machine learning")
    
    if result["success"]:
        console.print(f"\n[bold]Top papers:[/bold]")
        for i, p in enumerate(result["papers"][:3], 1):
            console.print(f"\n{i}. {p['title'][:80]}")
            authors = ", ".join(p["authors"]) if p["authors"] else "Unknown"
            console.print(f"   Authors: {authors}")
            console.print(f"   Published: {p['published']}")
            console.print(f"   Citations: {p.get('citation_count', 0)}")
            console.print(f"   URL: {p['url']}")
    else:
        console.print("[red]Agent failed[/red]")