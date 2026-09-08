"""
SERPER MBB WRAPPER
==================
ADR-023: MBB Corporate Standards Integration

Wraps Serper Google Search API to return MBB-structured intelligence reports:
1. Executive Summary (key finding + market impact)
2. Key Findings (MECE categories)
3. Supporting Evidence (source credibility ratings)

Serper API: https://serper.dev/
Environment Variable: SERPER_API_KEY

Authority: STIG (CTO)
Reference: ADR-023, ADR-012 (Economic Safety)
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urlparse
import logging

# Load environment
from dotenv import load_dotenv
load_dotenv('C:/fhq-market-system/vision-ios/.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SerperMBBWrapper:
    """
    Serper API wrapper with MBB structured output

    Transforms raw Google search results into pyramid-structured
    executive intelligence reports following McKinsey standards.

    Usage:
        serper = SerperMBBWrapper()
        result = serper.search_mbb("Federal Reserve interest rate decision")

        print(result['executive_summary']['key_finding'])
        # "Fed held rates at 5.25-5.50% (hawkish hold)"
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('SERPER_API_KEY')

        if not self.api_key:
            raise ValueError("SERPER_API_KEY not found in environment variables")

        self.base_url = "https://google.serper.dev/search"

        # Source credibility tiers (MBB standard)
        self.credibility_tiers = {
            # PRIMARY: Official government, regulatory sources
            "federalreserve.gov": "PRIMARY",
            "sec.gov": "PRIMARY",
            "treasury.gov": "PRIMARY",
            "bls.gov": "PRIMARY",
            "census.gov": "PRIMARY",

            # HIGH: Premium financial news, terminals
            "bloomberg.com": "HIGH",
            "wsj.com": "HIGH",
            "ft.com": "HIGH",
            "economist.com": "HIGH",

            # MEDIUM: Established news agencies
            "reuters.com": "MEDIUM",
            "cnbc.com": "MEDIUM",
            "apnews.com": "MEDIUM",
            "marketwatch.com": "MEDIUM",

            # LOW: Blogs, social media, unverified
            # (default for unlisted domains)
        }

    def search_mbb(self, query: str, num_results: int = 10, use_llm_synthesis: bool = True) -> Dict:
        """
        Execute search and return MBB-structured output

        Args:
            query: Search query string
            num_results: Number of results to fetch (max 100)
            use_llm_synthesis: If True, use LLM to synthesize results into narrative

        Returns:
            {
                "executive_summary": {
                    "key_finding": str,
                    "market_impact": str,
                    "recommendation": str
                },
                "key_findings_mece": {
                    "category_1": str,
                    "category_2": str,
                    ...
                },
                "supporting_evidence": [
                    {
                        "title": str,
                        "url": str,
                        "snippet": str,
                        "credibility": "PRIMARY" | "HIGH" | "MEDIUM" | "LOW"
                    }
                ],
                "serper_metadata": {
                    "query": str,
                    "num_results": int,
                    "timestamp": str
                }
            }
        """
        # Execute raw search
        raw_results = self._raw_search(query, num_results)

        if not raw_results:
            return self._empty_result(query)

        # Rate source credibility
        rated_evidence = self._rate_source_credibility(raw_results)

        # LLM synthesis (optional, expensive)
        if use_llm_synthesis:
            structured = self._synthesize_mbb_with_llm(raw_results, query, rated_evidence)
        else:
            structured = self._synthesize_mbb_heuristic(raw_results, query, rated_evidence)

        return structured

    def _raw_search(self, query: str, num_results: int) -> List[Dict]:
        """
        Execute Serper API search

        Returns list of organic search results
        """
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }

        payload = {
            'q': query,
            'num': min(num_results, 100),  # Serper max is 100
            'gl': 'us',  # Geolocation: US
            'hl': 'en'   # Language: English
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            organic = data.get('organic', [])

            logging.info(f"Serper search '{query}': {len(organic)} results")

            return organic

        except requests.exceptions.RequestException as e:
            logging.error(f"Serper API error: {e}")
            return []

    def _rate_source_credibility(self, results: List[Dict]) -> List[Dict]:
        """
        Rate source credibility (PRIMARY, HIGH, MEDIUM, LOW)

        MBB standard: Distinguish between official sources, premium news,
        established agencies, and unverified content.
        """
        rated = []

        for result in results:
            domain = self._extract_domain(result.get('link', ''))
            credibility = self.credibility_tiers.get(domain, "LOW")

            rated.append({
                "title": result.get('title', ''),
                "url": result.get('link', ''),
                "snippet": result.get('snippet', ''),
                "credibility": credibility,
                "position": result.get('position', 0)
            })

        # Sort by credibility tier, then position
        tier_order = {"PRIMARY": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        rated.sort(key=lambda x: (tier_order.get(x['credibility'], 4), x['position']))

        return rated

    def _synthesize_mbb_with_llm(
        self,
        raw_results: List[Dict],
        query: str,
        rated_evidence: List[Dict]
    ) -> Dict:
        """
        Use LLM (DeepSeek-R1 or GPT-4o) to synthesize results into MBB structure

        Prompt Engineering:
        "You are a McKinsey consultant. Synthesize search results
        into pyramid structure: executive summary first, then
        MECE key findings, then supporting evidence."
        """
        # Prepare evidence context for LLM
        evidence_context = "\n\n".join([
            f"[{ev['credibility']}] {ev['title']}\n{ev['snippet']}\nSource: {ev['url']}"
            for ev in rated_evidence[:5]  # Top 5 most credible
        ])

        # Construct LLM prompt
        prompt = f"""You are a McKinsey consultant analyzing market intelligence.

SEARCH QUERY: {query}

TOP SEARCH RESULTS (CREDIBILITY-RANKED):
{evidence_context}

TASK: Synthesize these results into a McKinsey-style executive intelligence report.

OUTPUT FORMAT (JSON):
{{
    "executive_summary": {{
        "key_finding": "[Single-sentence key finding]",
        "market_impact": "[Quantified market impact if available]",
        "recommendation": "[Actionable recommendation]"
    }},
    "key_findings_mece": {{
        "policy_decision": "[What was decided/announced]",
        "forward_guidance": "[Future outlook/guidance]",
        "market_reaction": "[How markets responded]"
    }}
}}

REQUIREMENTS:
1. Pyramid Principle: Answer first (executive summary), then support (findings)
2. MECE: Key findings must be mutually exclusive categories
3. Evidence-Based: Every claim references a source
4. Quantify when possible (percentages, basis points, dollar amounts)
5. Be concise and actionable

GENERATE REPORT:"""

        try:
            # Call LLM (DeepSeek-R1 via OpenAI-compatible API)
            synthesis = self._call_llm(prompt)

            # Parse LLM response (should be JSON)
            if isinstance(synthesis, str):
                synthesis = json.loads(synthesis)

            return {
                "executive_summary": synthesis.get("executive_summary", {}),
                "key_findings_mece": synthesis.get("key_findings_mece", {}),
                "supporting_evidence": rated_evidence,
                "serper_metadata": {
                    "query": query,
                    "num_results": len(raw_results),
                    "synthesis_method": "LLM",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

        except Exception as e:
            logging.error(f"LLM synthesis failed: {e}, falling back to heuristic")
            return self._synthesize_mbb_heuristic(raw_results, query, rated_evidence)

    def _synthesize_mbb_heuristic(
        self,
        raw_results: List[Dict],
        query: str,
        rated_evidence: List[Dict]
    ) -> Dict:
        """
        Fallback: Heuristic-based synthesis (no LLM, cheaper, faster)

        Uses top-ranked result as key finding, categorizes by source type
        """
        # Key finding: Use top-credibility result
        top_result = rated_evidence[0] if rated_evidence else {}

        key_finding = top_result.get('title', 'No results found')
        market_impact = "See supporting evidence for details"

        # Categorize by source type (MECE)
        primary_sources = [ev for ev in rated_evidence if ev['credibility'] == 'PRIMARY']
        high_sources = [ev for ev in rated_evidence if ev['credibility'] == 'HIGH']
        medium_sources = [ev for ev in rated_evidence if ev['credibility'] == 'MEDIUM']

        return {
            "executive_summary": {
                "key_finding": key_finding,
                "market_impact": market_impact,
                "recommendation": "Review supporting evidence for detailed analysis"
            },
            "key_findings_mece": {
                "official_sources": f"{len(primary_sources)} official sources",
                "premium_news": f"{len(high_sources)} premium news sources",
                "established_news": f"{len(medium_sources)} established news sources"
            },
            "supporting_evidence": rated_evidence,
            "serper_metadata": {
                "query": query,
                "num_results": len(raw_results),
                "synthesis_method": "HEURISTIC",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }

    def _call_llm(self, prompt: str) -> Dict:
        """
        Call LLM for synthesis (DeepSeek-R1 or GPT-4o)

        Returns parsed JSON response
        """
        # Use DeepSeek-R1 (default per ADR-012 Economic Safety)
        openai_api_key = os.getenv('OPENAI_API_KEY')
        deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')

        if deepseek_api_key:
            # DeepSeek-R1 via OpenAI-compatible API
            import openai
            client = openai.OpenAI(
                api_key=deepseek_api_key,
                base_url="https://api.deepseek.com/v1"
            )

            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": "You are a McKinsey consultant synthesizing market intelligence."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            content = response.choices[0].message.content

            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)

        else:
            raise ValueError("No LLM API key available (DEEPSEEK_API_KEY or OPENAI_API_KEY)")

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            return urlparse(url).netloc
        except:
            return ""

    def _empty_result(self, query: str) -> Dict:
        """Return empty result structure"""
        return {
            "executive_summary": {
                "key_finding": "No results found",
                "market_impact": "N/A",
                "recommendation": "Refine search query"
            },
            "key_findings_mece": {},
            "supporting_evidence": [],
            "serper_metadata": {
                "query": query,
                "num_results": 0,
                "synthesis_method": "NONE",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }


def main():
    """Test Serper MBB wrapper"""

    serper = SerperMBBWrapper()

    # Test query 1: Fed interest rate decision
    print("=" * 70)
    print("TEST: Federal Reserve Interest Rate Decision")
    print("=" * 70)

    result1 = serper.search_mbb(
        "Federal Reserve interest rate decision latest",
        num_results=10,
        use_llm_synthesis=False  # Use heuristic (cheaper)
    )

    print(json.dumps(result1, indent=2))

    # Test query 2: Market volatility
    print("\n" + "=" * 70)
    print("TEST: Market Volatility Analysis")
    print("=" * 70)

    result2 = serper.search_mbb(
        "S&P 500 VIX volatility index latest",
        num_results=10,
        use_llm_synthesis=False
    )

    print(json.dumps(result2, indent=2))


if __name__ == "__main__":
    main()
