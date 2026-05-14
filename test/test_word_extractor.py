"""
Unit tests for dlg.word_extractor module.

Tests cover:
- Successful extraction and deduplication
- Partial chunk failure (some chunks fail, some succeed)
- All chunks fail → all_failed=True
- Deduplication is case-insensitive
"""
import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dlg.word_extractor import extract_words, _deduplicate


# ── Minimal Word stub ─────────────────────────────────────────────────────────

class _Word:
    def __init__(self, english: str, translation: str):
        self.english = english
        self.translation = translation

    def __eq__(self, other):
        return (
            isinstance(other, _Word)
            and self.english == other.english
            and self.translation == other.translation
        )

    def __repr__(self):
        return f"Word({self.english!r}, {self.translation!r})"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _words(*pairs):
    """Build a list of _Word objects from (english, translation) tuples."""
    return [_Word(e, t) for e, t in pairs]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDeduplicate(unittest.TestCase):
    """_deduplicate removes exact and case-insensitive duplicates."""

    def test_no_duplicates_returned_as_is(self):
        words = _words(("dog", "hund"), ("cat", "kat"))
        result = _deduplicate(words)
        self.assertEqual(len(result), 2)

    def test_exact_duplicates_removed(self):
        words = _words(("dog", "hund"), ("dog", "hund"))
        result = _deduplicate(words)
        self.assertEqual(len(result), 1)

    def test_case_insensitive_deduplication(self):
        words = _words(("Dog", "Hund"), ("dog", "hund"))
        result = _deduplicate(words)
        self.assertEqual(len(result), 1)

    def test_same_english_different_translation_kept(self):
        words = _words(("dog", "hund"), ("dog", "valp"))
        result = _deduplicate(words)
        self.assertEqual(len(result), 2)

    def test_empty_list_returns_empty(self):
        self.assertEqual(_deduplicate([]), [])


class TestExtractWords(unittest.TestCase):
    """extract_words orchestrates LLM extraction across chunks."""

    def _make_agent(self, results):
        """Return a mock KnowledgeExtractionAgent.
        
        results: list of (list[_Word] | Exception) — one per chunk.
        """
        call_idx = [0]

        async def fake_extract(chunk):
            idx = call_idx[0]
            call_idx[0] += 1
            value = results[idx]
            if isinstance(value, Exception):
                raise value
            mock_result = MagicMock()
            mock_result.words = value
            return mock_result

        agent = MagicMock()
        agent._extract_knowledge_from_chunk = fake_extract
        return agent

    @patch("dlg.word_extractor.KnowledgeExtractionAgent")
    def test_single_chunk_success(self, MockAgent):
        words = _words(("dog", "hund"), ("cat", "kat"))
        MockAgent.return_value = self._make_agent([words])

        result, all_failed = run(extract_words(["some text"], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(len(result), 2)

    @patch("dlg.word_extractor.KnowledgeExtractionAgent")
    def test_deduplication_across_chunks(self, MockAgent):
        chunk1_words = _words(("dog", "hund"))
        chunk2_words = _words(("dog", "hund"), ("cat", "kat"))  # "dog/hund" is a duplicate
        MockAgent.return_value = self._make_agent([chunk1_words, chunk2_words])

        result, all_failed = run(extract_words(["chunk1", "chunk2"], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(len(result), 2)  # deduped: dog/hund + cat/kat

    @patch("dlg.word_extractor.KnowledgeExtractionAgent")
    def test_all_chunks_fail_sets_all_failed_true(self, MockAgent):
        # Both retry attempts raise, so the chunk is skipped
        MockAgent.return_value = self._make_agent(
            [RuntimeError("LLM down"), RuntimeError("LLM down")]
        )

        result, all_failed = run(extract_words(["chunk1"], "danish", object()))

        self.assertTrue(all_failed)
        self.assertEqual(result, [])

    @patch("dlg.word_extractor.KnowledgeExtractionAgent")
    def test_partial_failure_does_not_set_all_failed(self, MockAgent):
        # chunk1 fails twice (retry exhausted), chunk2 succeeds
        fail = RuntimeError("LLM error")
        success_words = _words(("dog", "hund"))
        MockAgent.return_value = self._make_agent(
            [fail, fail, success_words]
        )

        result, all_failed = run(extract_words(["chunk1", "chunk2"], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(len(result), 1)

    @patch("dlg.word_extractor.KnowledgeExtractionAgent")
    def test_empty_chunks_returns_empty_not_all_failed(self, MockAgent):
        MockAgent.return_value = MagicMock()

        result, all_failed = run(extract_words([], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
