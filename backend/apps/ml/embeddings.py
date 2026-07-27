"""Embedding service.

Loaded once per process and cached — a 22M-param MiniLM keeps p95 encode
latency under ~15 ms on CPU, which is what makes synchronous search viable.
"""
from __future__ import annotations

import functools
import hashlib
import logging

import numpy as np
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_encoder():
    from sentence_transformers import SentenceTransformer

    logger.info("loading embedding model %s", settings.EMBEDDING_MODEL)
    return SentenceTransformer(settings.EMBEDDING_MODEL)


@functools.lru_cache(maxsize=1)
def get_cross_encoder():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(settings.CROSS_ENCODER_MODEL)


def _key(text: str) -> str:
    return "emb:" + hashlib.sha1(text.encode("utf-8")).hexdigest()


def embed(text: str, use_cache: bool = True) -> list[float]:
    if use_cache and (hit := cache.get(_key(text))):
        return hit
    vec = get_encoder().encode(text, normalize_embeddings=True).tolist()
    if use_cache:
        cache.set(_key(text), vec, timeout=60 * 60 * 24)
    return vec


def embed_batch(texts: list[str], batch_size: int = 64) -> np.ndarray:
    return get_encoder().encode(
        texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=True
    )


def rerank(query: str, passages: list[str]) -> list[float]:
    """Cross-encoder rerank. Bi-encoder recall is cheap but imprecise;
    reranking the top-25 down to top-5 is where answer quality comes from."""
    if not passages:
        return []
    pairs = [(query, p) for p in passages]
    return [float(s) for s in get_cross_encoder().predict(pairs)]
