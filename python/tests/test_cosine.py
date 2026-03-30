"""Tests for TF-IDF cosine similarity loop detection."""

from reivo_guard.cosine import (
    CosineLoopResult,
    detect_loop_by_cosine,
    _tokenize,
    _cosine_similarity,
    _build_tfidf_vectors,
)


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_filters_single_char(self):
        tokens = _tokenize("I am a developer")
        assert "i" not in tokens
        assert "a" not in tokens
        assert "am" in tokens

    def test_splits_on_punctuation(self):
        tokens = _tokenize("what's the capital?")
        assert "what" in tokens
        assert "the" in tokens
        assert "capital" in tokens


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = {"hello": 1.0, "world": 1.0}
        sim = _cosine_similarity(a, a)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = {"hello": 1.0}
        b = {"world": 1.0}
        sim = _cosine_similarity(a, b)
        assert sim == 0.0

    def test_empty_vectors(self):
        assert _cosine_similarity({}, {}) == 0.0
        assert _cosine_similarity({"a": 1.0}, {}) == 0.0


class TestDetectLoopByCosine:
    def test_not_enough_history(self):
        result = detect_loop_by_cosine(["hello"], "hello again")
        assert not result.is_loop
        assert result.match_count == 0

    def test_no_loop_different_topics(self):
        prompts = [
            "How do I sort a list in Python?",
            "What is the weather in Tokyo?",
            "Explain quantum computing",
        ]
        result = detect_loop_by_cosine(prompts, "Tell me about cooking pasta")
        assert not result.is_loop

    def test_detects_semantic_loop_custom_threshold(self):
        # With a lower threshold, semantically similar prompts are caught
        prompts = [
            "How do I sort a list in Python?",
            "How do I sort a list in Python please?",
            "How do I sort a list in Python quickly?",
            "How do I sort a list in Python easily?",
            "How do I sort a list in Python efficiently?",
        ]
        result = detect_loop_by_cosine(
            prompts, "How do I sort a list in Python now?",
            threshold=0.5, match_threshold=1,
        )
        assert result.is_loop
        assert result.match_count >= 2
        assert result.similarity is not None
        assert result.similarity > 0.5

    def test_high_similarity_with_minor_variation(self):
        # Even with default threshold, closely worded prompts should score high
        prompts = [
            "sort a list in Python",
            "sort Python list",
            "Python list sorting",
        ]
        result = detect_loop_by_cosine(prompts, "sort a Python list")
        assert result.similarity is not None
        assert result.similarity > 0.3  # meaningful similarity

    def test_similarity_returned(self):
        prompts = [
            "What is Python?",
            "Tell me about Python",
            "Explain Python to me",
        ]
        result = detect_loop_by_cosine(prompts, "What is Python programming?")
        assert result.similarity is not None
        assert 0 <= result.similarity <= 1.0

    def test_custom_threshold(self):
        prompts = [
            "sort a list",
            "sort a list please",
            "sorting lists",
            "list sorting",
        ]
        # Very low threshold should trigger easily
        result = detect_loop_by_cosine(prompts, "sort lists", threshold=0.3, match_threshold=2)
        assert result.is_loop

    def test_exact_duplicates_detected(self):
        prompt = "What is the capital of France?"
        prompts = [prompt] * 5
        result = detect_loop_by_cosine(prompts, prompt)
        assert result.is_loop
        assert result.similarity is not None
        assert result.similarity > 0.99

    def test_result_dataclass(self):
        result = CosineLoopResult(is_loop=True, match_count=5, similarity=0.95)
        assert result.is_loop
        assert result.match_count == 5
        assert result.similarity == 0.95
