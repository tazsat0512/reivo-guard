"""TF-IDF cosine similarity loop detection — pure Python, zero dependencies.

Detects semantically similar prompts even when worded differently.
Port of the TypeScript implementation in ts/src/loop-detector.ts.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


LOOP_COSINE_THRESHOLD = 0.92
LOOP_COSINE_MIN_HISTORY = 2
LOOP_COSINE_MATCH_THRESHOLD = 4  # LOOP_HASH_THRESHOLD - 1


@dataclass
class CosineLoopResult:
    """Result of cosine similarity loop detection."""

    is_loop: bool
    match_count: int
    similarity: Optional[float] = None


def detect_loop_by_cosine(
    previous_prompts: list[str],
    current_prompt: str,
    threshold: float = LOOP_COSINE_THRESHOLD,
    match_threshold: int = LOOP_COSINE_MATCH_THRESHOLD,
) -> CosineLoopResult:
    """Detect loops using TF-IDF cosine similarity.

    Args:
        previous_prompts: List of previous prompt texts.
        current_prompt: The new prompt to check.
        threshold: Cosine similarity threshold (0-1). Default 0.92.
        match_threshold: Number of similar prompts to trigger loop. Default 4.

    Returns:
        CosineLoopResult with is_loop, match_count, and max similarity.
    """
    if len(previous_prompts) < LOOP_COSINE_MIN_HISTORY:
        return CosineLoopResult(is_loop=False, match_count=0)

    all_docs = previous_prompts + [current_prompt]
    vectors = _build_tfidf_vectors(all_docs)
    current_vector = vectors[-1]

    max_sim = 0.0
    high_sim_count = 0

    for i in range(len(vectors) - 1):
        sim = _cosine_similarity(current_vector, vectors[i])
        if sim > max_sim:
            max_sim = sim
        if sim >= threshold:
            high_sim_count += 1

    return CosineLoopResult(
        is_loop=high_sim_count >= match_threshold,
        match_count=high_sim_count + 1,
        similarity=max_sim,
    )


_TOKEN_RE = re.compile(r"\W+")


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-word boundaries, filter short tokens."""
    return [t for t in _TOKEN_RE.split(text.lower()) if len(t) > 1]


def _build_tfidf_vectors(docs: list[str]) -> list[dict[str, float]]:
    """Build TF-IDF vectors for a list of documents.

    Falls back to raw TF when IDF collapses (all terms appear in all docs).
    """
    tokenized = [_tokenize(doc) for doc in docs]

    # Document frequency
    df: dict[str, int] = {}
    for tokens in tokenized:
        for token in set(tokens):
            df[token] = df.get(token, 0) + 1

    n = len(docs)
    vectors: list[dict[str, float]] = []

    for tokens in tokenized:
        if not tokens:
            vectors.append({})
            continue

        # Term frequency
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        # TF-IDF with smoothed IDF: log(1 + n/df) ensures common terms
        # still contribute to similarity (unlike log(n/df) which gives 0)
        vector: dict[str, float] = {}
        token_count = len(tokens)
        for token, freq in tf.items():
            idf = math.log(1 + n / df.get(token, 1))
            vector[token] = (freq / token_count) * idf
        vectors.append(vector)

    return vectors


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for key, val_a in a.items():
        norm_a += val_a * val_a
        val_b = b.get(key)
        if val_b is not None:
            dot_product += val_a * val_b

    for val_b in b.values():
        norm_b += val_b * val_b

    magnitude = math.sqrt(norm_a) * math.sqrt(norm_b)
    return 0.0 if magnitude == 0 else dot_product / magnitude
