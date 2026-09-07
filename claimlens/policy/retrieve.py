"""Illustrative policy clause retrieval engine using lightweight TF-IDF cosine similarity.

Guarantees:
- Real text retrieval with zero reliance on paid LLM APIs.
- Explicit 'NOT ESTABLISHED' fallback when queries do not match sample clauses.
- Clearly labeled illustrative citations.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_POLICY_DIR = Path("data/policy_clauses")
MIN_RELEVANCE_THRESHOLD = 0.12

POLICY_DISCLAIMER = (
    "ILLUSTRATIVE ONLY. Non-legal sample policy text for portfolio demonstration purposes. "
    "Does not constitute legal, regulatory, or insurance underwriting advice."
)

STOPWORDS: set[str] = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "he",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "shall",
    "under",
    "upon",
    "or",
    "such",
    "than",
    "this",
    "can",
    "into",
}


@dataclass(frozen=True)
class PolicyClause:
    id: str
    title: str
    citation: str
    text: str
    keywords: list[str] = field(default_factory=list)


@dataclass
class PolicyRetrievalResult:
    query: str
    is_established: bool
    matched_clause: PolicyClause | None
    relevance_score: float
    citation: str
    title: str
    text: str
    guidance: str
    disclaimer: str = POLICY_DISCLAIMER


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-z0-9-]+\b", text.lower())
    return [t for t in tokens if len(t) > 1 and t not in STOPWORDS]


class PolicyRetriever:
    """Lightweight TF-IDF document retriever for policy clauses."""

    def __init__(self, clauses_dir: Path | str | None = None) -> None:
        self.clauses_dir = Path(clauses_dir) if clauses_dir else DEFAULT_POLICY_DIR
        self.clauses: list[PolicyClause] = []
        self.doc_tokens: list[list[str]] = []
        self.doc_freqs: Counter[str] = Counter()
        self.num_docs = 0
        self.load_clauses()

    def load_clauses(self) -> None:
        self.clauses = []
        self.doc_tokens = []
        self.doc_freqs = Counter()

        if not self.clauses_dir.exists():
            return

        for path in sorted(self.clauses_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            clause = PolicyClause(
                id=data["id"],
                title=data["title"],
                citation=data["citation"],
                text=data["text"],
                keywords=data.get("keywords", []),
            )
            self.clauses.append(clause)

            # Combined content for indexing
            full_text = f"{clause.title} {clause.text} {' '.join(clause.keywords)}"
            tokens = _tokenize(full_text)
            self.doc_tokens.append(tokens)
            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.doc_freqs[t] += 1

        self.num_docs = len(self.clauses)

    def _compute_vector(self, tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        vec: dict[str, float] = {}
        for token, count in tf.items():
            df = self.doc_freqs.get(token, 0)
            idf = math.log((1.0 + self.num_docs) / (1.0 + df)) + 1.0
            vec[token] = (count / max(1, len(tokens))) * idf

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec.values()))
        if norm > 0:
            vec = {k: v / norm for k, v in vec.items()}
        return vec

    def search(
        self,
        query: str,
        threshold: float = MIN_RELEVANCE_THRESHOLD,
    ) -> PolicyRetrievalResult:
        query_tokens = _tokenize(query)
        if not query_tokens or not self.clauses:
            return PolicyRetrievalResult(
                query=query,
                is_established=False,
                matched_clause=None,
                relevance_score=0.0,
                citation="Not Established",
                title="Clause Not Established",
                text="No applicable clause found matching the submitted query.",
                guidance="The query does not correspond to standard total-loss, glass, repair, or structural clauses in the illustrative policy repository.",
            )

        query_vec = self._compute_vector(query_tokens)
        best_clause: PolicyClause | None = None
        best_score = 0.0

        for clause, tokens in zip(self.clauses, self.doc_tokens, strict=False):
            doc_vec = self._compute_vector(tokens)
            # Dot product (cosine similarity since vectors are L2-normalized)
            common = set(query_vec.keys()) & set(doc_vec.keys())
            score = sum(query_vec[k] * doc_vec[k] for k in common)

            if score > best_score:
                best_score = score
                best_clause = clause

        if best_clause is None or best_score < threshold:
            return PolicyRetrievalResult(
                query=query,
                is_established=False,
                matched_clause=None,
                relevance_score=round(best_score, 4),
                citation="Not Established",
                title="Clause Not Established",
                text="No applicable clause found matching the submitted query.",
                guidance=(
                    f"Highest match score ({best_score:.3f}) fell below the certainty threshold ({threshold:.2f}). "
                    "ClaimLens abstains from citing speculative legal text."
                ),
            )

        return PolicyRetrievalResult(
            query=query,
            is_established=True,
            matched_clause=best_clause,
            relevance_score=round(best_score, 4),
            citation=best_clause.citation,
            title=best_clause.title,
            text=best_clause.text,
            guidance=f"Relevant policy standard cited from {best_clause.citation} based on matched collision criteria.",
        )


_DEFAULT_RETRIEVER: PolicyRetriever | None = None


def get_retriever() -> PolicyRetriever:
    global _DEFAULT_RETRIEVER
    if _DEFAULT_RETRIEVER is None:
        _DEFAULT_RETRIEVER = PolicyRetriever()
    return _DEFAULT_RETRIEVER


def retrieve_policy_guidance(query: str) -> PolicyRetrievalResult:
    """Public convenience function for querying the policy repository."""
    return get_retriever().search(query)
