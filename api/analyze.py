"""
PlagIA 2 — Serverless Analysis Function
Vercel Python Runtime: searches 5 academic APIs + computes similarity
"""
import json
import re
import hashlib
import asyncio
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
import httpx


# ============================================
# ACADEMIC API SOURCES
# ============================================

async def search_openalex(query: str, max_results: int = 5) -> list:
    params = {"search": query, "per_page": max_results, "sort": "relevance_score:desc"}
    headers = {"User-Agent": "PlagIA/2.0 (checkone076@gmail.com)"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get("https://api.openalex.org/works", params=params, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        papers = []
        for work in data.get("results", []):
            abstract = ""
            if work.get("abstract_inverted_index"):
                inverted = work["abstract_inverted_index"]
                words = [""] * (max(pos for positions in inverted.values() for pos in positions) + 1)
                for word, positions in inverted.items():
                    for pos in positions:
                        if pos < len(words):
                            words[pos] = word
                abstract = " ".join(w for w in words if w)
            papers.append({
                "source": "OpenAlex",
                "title": work.get("title", "Unknown"),
                "abstract": abstract,
                "url": work.get("doi") or work.get("id", "")
            })
        return papers
    except Exception as e:
        print(f"OpenAlex error: {e}")
        return []


async def search_crossref(query: str, max_results: int = 5) -> list:
    params = {"query": query, "rows": max_results, "sort": "relevance"}
    headers = {"User-Agent": "PlagIA/2.0 (mailto:checkone076@gmail.com)"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get("https://api.crossref.org/works", params=params, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        papers = []
        for item in data.get("message", {}).get("items", []):
            title = (item.get("title") or ["Unknown"])[0]
            abstract = item.get("abstract", "")
            # Clean HTML from CrossRef abstracts
            abstract = re.sub(r'<[^>]+>', '', abstract)
            doi = item.get("DOI", "")
            papers.append({
                "source": "CrossRef",
                "title": title,
                "abstract": abstract,
                "url": f"https://doi.org/{doi}" if doi else ""
            })
        return papers
    except Exception as e:
        print(f"CrossRef error: {e}")
        return []


async def search_arxiv(query: str, max_results: int = 3) -> list:
    import xml.etree.ElementTree as ET
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get("https://export.arxiv.org/api/query", params=params)
            resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        papers = []
        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns)
            summary = entry.find('atom:summary', ns)
            link = entry.find('atom:id', ns)
            if title is not None and summary is not None:
                papers.append({
                    "source": "arXiv",
                    "title": title.text.strip(),
                    "abstract": summary.text.strip(),
                    "url": link.text if link is not None else ""
                })
        return papers
    except Exception as e:
        print(f"arXiv error: {e}")
        return []


async def search_semantic_scholar(query: str, max_results: int = 3) -> list:
    params = {
        "query": query,
        "limit": max_results,
        "fields": "paperId,title,abstract,url,authors,year"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params)
            resp.raise_for_status()
        data = resp.json()
        papers = []
        for paper in data.get("data", []):
            papers.append({
                "source": "Semantic Scholar",
                "title": paper.get("title", "Unknown"),
                "abstract": paper.get("abstract") or "",
                "url": f"https://www.semanticscholar.org/paper/{paper.get('paperId', '')}"
            })
        return papers
    except Exception as e:
        print(f"Semantic Scholar error: {e}")
        return []


async def search_pubmed(query: str, max_results: int = 3) -> list:
    try:
        # Step 1: Search for IDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params=search_params)
            resp.raise_for_status()
        search_data = resp.json()
        ids = search_data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # Step 2: Fetch details
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            "rettype": "abstract"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", params=fetch_params)
            resp.raise_for_status()
        detail_data = resp.json()

        papers = []
        for uid in ids:
            doc = detail_data.get("result", {}).get(uid, {})
            if doc:
                papers.append({
                    "source": "PubMed",
                    "title": doc.get("title", "Unknown"),
                    "abstract": doc.get("sorttitle", ""),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"
                })
        return papers
    except Exception as e:
        print(f"PubMed error: {e}")
        return []


async def search_web(query: str, max_results: int = 3) -> list:
    """Search DuckDuckGo for web sources"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PlagIA/2.0)"}
        params = {"q": query, "format": "json", "no_html": 1, "no_redirect": 1}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get("https://api.duckduckgo.com/", params=params, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        papers = []
        for topic in (data.get("RelatedTopics") or [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                papers.append({
                    "source": "Web",
                    "title": topic.get("Text", "")[:100],
                    "abstract": topic.get("Text", ""),
                    "url": topic.get("FirstURL", "")
                })
        return papers
    except Exception as e:
        print(f"Web search error: {e}")
        return []


# ============================================
# SIMILARITY ENGINE
# ============================================

def minhash_similarity(text1: str, text2: str, num_perm: int = 128) -> float:
    """MinHash Jaccard similarity"""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.0

    # Simple Jaccard (word-level)
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def ngram_similarity(text1: str, text2: str, n: int = 3) -> float:
    """N-gram overlap similarity (better than word-level for paraphrasing)"""
    def get_ngrams(text, n):
        words = text.lower().split()
        return set(' '.join(words[i:i+n]) for i in range(len(words) - n + 1))

    ng1 = get_ngrams(text1, n)
    ng2 = get_ngrams(text2, n)
    if not ng1 or not ng2:
        return 0.0
    intersection = ng1 & ng2
    union = ng1 | ng2
    return len(intersection) / len(union) if union else 0.0


async def semantic_similarity_hf(text1: str, text2: str) -> float:
    """Use HuggingFace Inference API for free semantic similarity"""
    import os
    hf_token = os.environ.get("HF_TOKEN", "")

    try:
        headers = {"Content-Type": "application/json"}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"

        payload = {
            "inputs": {
                "source_sentence": text1[:500],
                "sentences": [text2[:500]]
            }
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2",
                headers=headers,
                json=payload
            )
            if resp.status_code == 200:
                scores = resp.json()
                if isinstance(scores, list) and len(scores) > 0:
                    return float(scores[0])
        return 0.0
    except Exception:
        return 0.0


# ============================================
# AI DETECTION (Heuristic)
# ============================================

def detect_ai_heuristic(text: str) -> dict:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 3]
    if len(sentences) < 2:
        return {"score": 0, "level": "low", "sentences": []}

    score = 0
    lengths = [len(s.split()) for s in sentences]
    mean_len = sum(lengths) / len(lengths)

    # Uniformity
    if len(lengths) > 2:
        std = (sum((l - mean_len)**2 for l in lengths) / len(lengths)) ** 0.5
        cv = std / mean_len if mean_len > 0 else 0
        if cv < 0.25:
            score += 35
        elif cv < 0.4:
            score += 20

    # Transitions
    transitions = ['however', 'moreover', 'furthermore', 'additionally', 'consequently',
                   'therefore', 'nevertheless', 'cependant', 'néanmoins', 'par conséquent',
                   'en outre', 'de plus', 'ainsi', 'toutefois', 'in conclusion']
    lower = text.lower()
    trans_count = sum(1 for t in transitions if t in lower)
    if trans_count > 4:
        score += 25
    elif trans_count > 2:
        score += 15

    # Repetitive starts
    starts = [s.split()[0].lower() for s in sentences if s.split()]
    unique_ratio = len(set(starts)) / len(starts) if starts else 1
    if unique_ratio < 0.4:
        score += 20
    elif unique_ratio < 0.6:
        score += 10

    # Sentence length range
    if 14 < mean_len < 26:
        score += 10

    score = min(score, 95)
    level = "high" if score > 70 else "medium" if score > 40 else "low"

    # Perplexity estimate
    words = text.split()
    unique_ratio_w = len(set(words)) / len(words) if words else 0
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0
    perplexity = 20 + (unique_ratio_w * 60) + (avg_word_len * 3)

    # Burstiness
    burstiness = (sum((l - mean_len)**2 for l in lengths) / len(lengths))**0.5 / mean_len if mean_len > 0 else 0

    sentence_analysis = []
    for i, s in enumerate(sentences[:20]):
        s_words = s.split()
        s_unique = len(set(s_words)) / len(s_words) if s_words else 0
        s_perplexity = 20 + (s_unique * 60) + (sum(len(w) for w in s_words) / len(s_words) * 3) if s_words else 50
        s_score = max(0, 100 - (s_perplexity * 1.2)) * 0.4 + score * 0.6
        s_score = min(95, max(0, s_score))
        sentence_analysis.append({
            "text": s,
            "position": i,
            "ai_score": round(s_score, 1),
            "perplexity": round(s_perplexity, 1),
            "level": "high" if s_score > 70 else "medium" if s_score > 40 else "low"
        })

    return {
        "score": round(score, 1),
        "level": level,
        "metrics": {
            "perplexity": round(perplexity, 2),
            "burstiness": round(burstiness, 3),
            "perplexity_score": round(max(0, 100 - perplexity * 1.2), 1),
            "burstiness_score": round(max(0, 100 - burstiness * 200), 1)
        },
        "sentences": sentence_analysis
    }


# ============================================
# MAIN ANALYSIS
# ============================================

async def run_analysis(text: str) -> dict:
    keywords = " ".join(text.split()[:20])

    # Search all 5 academic APIs + web in parallel
    results = await asyncio.gather(
        search_openalex(keywords, 5),
        search_crossref(keywords, 5),
        search_arxiv(keywords, 3),
        search_semantic_scholar(keywords, 3),
        search_pubmed(keywords, 3),
        search_web(keywords, 3),
        return_exceptions=True
    )

    all_sources = []
    api_status = {}
    api_names = ["OpenAlex", "CrossRef", "arXiv", "Semantic Scholar", "PubMed", "Web"]
    for name, result in zip(api_names, results):
        if isinstance(result, list):
            all_sources.extend(result)
            api_status[name] = len(result)
        else:
            api_status[name] = f"error: {str(result)[:50]}"

    # Plagiarism detection
    matches = []
    highlighted_passages = []
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 3]

    for source in all_sources:
        source_text = source.get("abstract", "")
        if not source_text or len(source_text) < 20:
            continue

        # Word-level Jaccard
        word_sim = minhash_similarity(text, source_text)
        # N-gram similarity
        ngram_sim = ngram_similarity(text, source_text, 3)
        # Try HuggingFace semantic similarity
        semantic_sim = await semantic_similarity_hf(text[:500], source_text[:500])

        combined = max(word_sim, ngram_sim * 1.2, semantic_sim * 0.85)

        if combined > 0.12:
            match_type = "exact_copy" if word_sim > 0.6 else "paraphrase" if semantic_sim > 0.5 else "similar"
            matches.append({
                "source": source["source"],
                "title": source["title"],
                "url": source.get("url", ""),
                "similarity": round(combined * 100, 1),
                "word_similarity": round(word_sim * 100, 1),
                "semantic_similarity": round(semantic_sim * 100, 1),
                "type": match_type
            })

            # Passage-level for semantic matches
            if semantic_sim > 0.3:
                for i, sent in enumerate(sentences[:10]):
                    sent_sim = await semantic_similarity_hf(sent, source_text[:300])
                    if sent_sim > 0.35:
                        highlighted_passages.append({
                            "text": sent,
                            "position": i,
                            "similarity": round(sent_sim * 100, 1),
                            "source": source["title"],
                            "type": "exact" if sent_sim > 0.7 else "paraphrase"
                        })

    matches.sort(key=lambda x: x["similarity"], reverse=True)
    matches = matches[:15]

    # Deduplicate passages
    seen = set()
    unique_passages = []
    for p in sorted(highlighted_passages, key=lambda x: x["similarity"], reverse=True):
        if p["text"] not in seen:
            unique_passages.append(p)
            seen.add(p["text"])
    highlighted_passages = unique_passages[:20]

    plag_score = matches[0]["similarity"] if matches else 0
    plag_level = "high" if plag_score > 50 else "medium" if plag_score > 25 else "low"

    # AI detection
    ai_result = detect_ai_heuristic(text)

    # Corrections
    corrections = []
    for m in matches[:5]:
        if m["similarity"] > 20:
            corrections.append({
                "source": m["title"],
                "type": m["type"],
                "severity": "high" if m["similarity"] > 50 else "medium",
                "suggestion": f"Cite ou reformule: {m['title'][:80]}"
            })

    return {
        "plagiarism": {
            "score": round(plag_score, 1),
            "level": plag_level,
            "matches": matches,
            "highlighted_passages": highlighted_passages
        },
        "ai_detection": ai_result,
        "corrections": corrections,
        "sources_checked": len(all_sources),
        "api_status": api_status
    }


# ============================================
# VERCEL HANDLER
# ============================================

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
            text = data.get("text", "")

            if not text or len(text) < 50:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Texte trop court (min 50 caractères)"}).encode())
                return

            # Run async analysis
            result = asyncio.run(run_analysis(text))

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
