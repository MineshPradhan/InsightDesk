"""Build the retrieval knowledge base.

Dataset: https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset
27k intent-labelled question/answer pairs across e-commerce, billing, shipping,
accounts and refunds — CDLA-Sharing-1.0.

Answers are grouped by intent into articles, chunked, embedded and stored as
pgvector rows. That is the corpus every RAG draft is grounded in.

    python scripts/build_kb.py --per-intent 40
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.utils.text import slugify  # noqa: E402

from apps.ml.embeddings import embed_batch  # noqa: E402
from apps.rag.chunker import chunk  # noqa: E402
from apps.tickets.models import KBArticle, KBChunk  # noqa: E402

HF_DATASET = "bitext/Bitext-customer-support-llm-chatbot-training-dataset"
PLACEHOLDER = ["{{Order Number}}", "{{Customer Support Phone Number}}", "{{Website URL}}"]


def clean(text: str) -> str:
    for token in PLACEHOLDER:
        text = text.replace(token, token.strip("{}"))
    return " ".join(text.split())


def main(per_intent: int) -> None:
    from datasets import load_dataset

    df = load_dataset(HF_DATASET, split="train").to_pandas()
    print(f"loaded {len(df)} q/a pairs, {df['intent'].nunique()} intents")

    articles, chunk_rows, chunk_texts = [], [], []
    for (category, intent), group in df.groupby(["category", "intent"]):
        answers = [clean(a) for a in group["response"].head(per_intent).tolist()]
        questions = group["instruction"].head(8).tolist()
        body = (
            f"Common phrasings customers use: {'; '.join(questions)}\n\n"
            + "\n\n".join(dict.fromkeys(answers))
        )
        article = KBArticle(
            slug=slugify(f"{category}-{intent}")[:160],
            title=intent.replace("_", " ").title(),
            body=body,
            category=str(category).lower(),
            intent=str(intent),
            source_url=f"https://huggingface.co/datasets/{HF_DATASET}",
        )
        articles.append(article)

    KBArticle.objects.bulk_create(articles, ignore_conflicts=True)
    saved = KBArticle.objects.in_bulk(field_name="slug")
    print(f"created {len(saved)} articles")

    for article in saved.values():
        for i, piece in enumerate(chunk(article.body)):
            chunk_rows.append(KBChunk(article=article, chunk_index=i, text=piece))
            chunk_texts.append(piece)

    print(f"embedding {len(chunk_texts)} chunks…")
    vectors = embed_batch(chunk_texts)
    for row, vec in zip(chunk_rows, vectors, strict=True):
        row.vector = vec.tolist()

    KBChunk.objects.bulk_create(chunk_rows, batch_size=500, ignore_conflicts=True)
    print(f"stored {len(chunk_rows)} chunks. KB is live.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--per-intent", type=int, default=40)
    main(p.parse_args().per_intent)
