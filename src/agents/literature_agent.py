"""Literature Agent — searches academic papers (Crossref + OpenAlex + Semantic Scholar)"""
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
CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"

USER_AGENT = "DiscoveryLab/1.0 (mailto:vs9502778@gmail.com)"
MAILTO = "vs9502778@gmail.com"


class LiteratureAgent:
    """Searches papers via Crossref → OpenAlex → Semantic Scholar"""

    def __init__(self, max_results: int = 10, output_dir: str = "./data/papers"):
        self.max_results = max_results
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────────────────────
    # SOURCE 1: Crossref (primary — most reliable)
    # ─────────────────────────────────────────────────────────
    def _search_crossref(self, query: str, n: int) -> List[Dict]:
        params = {
            "query": query,
            "rows": n,
            "mailto": MAILTO,  # polite pool — 10 req/sec
            "select": "title,author,abstract,DOI,URL,issued,container-title,is-referenced-by-count",
        }
        headers = {"User-Agent": USER_AGENT}

        resp = requests.get(CROSSREF_API, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        papers = []
        for item in data.get("message", {}).get("items", []):
            # Authors
            authors = []
            for a in (item.get("author") or [])[:3]:
                name = " ".join(filter(None, [a.get("given"), a.get("family")]))
                if name:
                    authors.append(name)

            # Year
            year = ""
            for key in ("published-print", "published-online", "issued"):
                if item.get(key, {}).get("date-parts"):
                    year = str(item[key]["date-parts"][0][0])
                    break

            # Title (list → str)
            title = item.get("title", [""])
            title = title[0] if isinstance(title, list) and title else str(title)

            papers.append({
                "title": title,
                "authors": authors,
                "abstract": item.get("abstract", "") or "",
                "published": year,
                "doi": item.get("DOI", ""),
                "url": item.get("URL", ""),
                "venue": (item.get("container-title") or [""])[0] if item.get("container-title") else "",
                "citation_count": item.get("is-referenced-by-count", 0),
                "source": "crossref",
            })
        return papers

    # ─────────────────────────────────────────────────────────
    # SOURCE 2: OpenAlex (fallback)
    # ─────────────────────────────────────────────────────────
    def _search_openalex(self, query: str, n: int) -> List[Dict]:
        params = {
            "search": query,
            "per-page": n,
            "mailto": MAILTO,
        }
        headers = {"User-Agent": USER_AGENT}

        resp = requests.get(OPENALEX_API, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        papers = []
        for p in data.get("results", []):
            authors = []
            for a in (p.get("authorships") or [])[:3]:
                if a.get("author", {}).get("display_name"):
                    authors.append(a["author"]["display_name"])

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

    # ─────────────────────────────────────────────────────────
    # SOURCE 3: Semantic Scholar (last resort)
    # ─────────────────────────────────────────────────────────
    def _search_semantic_scholar(self, query: str, n: int) -> List[Dict]:
        params = {
            "query": query,
            "limit": min(n, 20),
            "fields": "title,abstract,authors,year,venue,externalIds,url,citationCount",
        }
        headers = {"User-Agent": USER_AGENT}

        resp = requests.get(SEMANTIC_SCHOLAR_API, params=params, headers=headers, timeout=30)
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
                "source": "semantic_scholar",
            })
        return papers

    # ─────────────────────────────────────────────────────────
    # Helper
    # ─────────────────────────────────────────────────────────
    def _reconstruct_abstract(self, inverted_index) -> str:
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

    # ─────────────────────────────────────────────────────────
    # MAIN SEARCH — tries all 3 sources with retry
    # ─────────────────────────────────────────────────────────
    def search(self, query: str, max_results: int = None) -> List[Dict]:
        n = max_results or self.max_results

        console.print(f"\n[cyan]📚 Searching papers:[/cyan] {query}")
        console.print(f"   Max results: {n}")

        # Sources in priority order
        sources = [
            ("Crossref", self._search_crossref),
            ("OpenAlex", self._search_openalex),
            ("Semantic Scholar", self._search_semantic_scholar),
        ]

        for name, fn in sources:
            try:
                console.print(f"   [dim]Trying {name}...[/dim]")
                papers = fn(query, n)

                if papers:
                    # Filter empty titles
                    papers = [p for p in papers if p.get("title")]
                    console.print(f"   [green]✅ {name}: {len(papers)} papers[/green]")
                    return papers[:n]
                else:
                    console.print(f"   [yellow]{name}: 0 results[/yellow]")

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else "?"
                console.print(f"   [yellow]{name} failed ({status})[/yellow]")
                # Exponential backoff on 429
                if status == 429:
                    wait = 3
                    console.print(f"   [dim]Rate limited — waiting {wait}s...[/dim]")
                    time.sleep(wait)
            except Exception as e:
                console.print(f"   [yellow]{name} failed: {str(e)[:80]}[/yellow]")

        console.print("   [red]❌ All sources failed[/red]")
        return []

    def save_papers(self, papers: List[Dict], query: str) -> str:
        safe_name = "".join(c if c.isalnum() else "_" for c in query)[:50]
        file = self.output_dir / f"{safe_name}.json"
        file.write_text(json.dumps(papers, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"   [green]💾 Saved: {file}[/green]")
        return str(file)

    def run(self, query: str) -> Dict:
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
            console.print(f"   Source: {p.get('source', '?')}")
            console.print(f"   URL: {p['url']}")
    else:
        console.print("[red]Agent failed[/red]")