import pytest

from apps.ml.classifier import _priority, _sentiment
from apps.rag.chunker import chunk
from apps.rag.pipeline import _validate_citations


def test_chunker_keeps_sentences_whole():
    text = " ".join(f"Sentence number {i} is here." for i in range(60))
    pieces = chunk(text, max_chars=200)
    assert len(pieces) > 1
    assert all(p.endswith(".") for p in pieces)


def test_chunker_empty():
    assert chunk("   ") == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Our production system is down, this is urgent", "critical"),
        ("I was charged twice, please refund asap", "high"),
        ("Just wondering about the roadmap, no rush", "low"),
        ("How do I change my display name?", "medium"),
    ],
)
def test_priority_cues(text, expected):
    level, conf, _ = _priority(text, _sentiment(text))
    assert level == expected
    assert 0 < conf <= 1


def test_sentiment_direction():
    assert _sentiment("this is terrible and unacceptable") < 0
    assert _sentiment("thanks, that was really helpful") > 0


@pytest.mark.parametrize(
    "reply,n,ok",
    [("Per [1] you can reset it.", 3, True), ("See [7].", 3, False), ("No citation.", 3, False)],
)
def test_citation_validation(reply, n, ok):
    assert _validate_citations(reply, n) is ok
