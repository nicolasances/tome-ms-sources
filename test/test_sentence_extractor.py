"""
Unit tests for dlg.sentence_extractor module.

Tests cover:
- Successful extraction and deduplication
- Chunk failure handling
- Deduplication is case-insensitive on the sentence field
- verify_sentences returns original list when verification fails (non-fatal)
"""
import asyncio
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dlg.sentence_extractor import extract_sentences, verify_sentences, _deduplicate


# ── Minimal SentencePair stub ─────────────────────────────────────────────────

class _SentencePair:
    def __init__(self, sentence: str, translation: str):
        self.sentence = sentence
        self.translation = translation

    def __eq__(self, other):
        return (
            isinstance(other, _SentencePair)
            and self.sentence == other.sentence
            and self.translation == other.translation
        )

    def __repr__(self):
        return f"SentencePair({self.sentence!r})"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pairs(*items):
    return [_SentencePair(s, t) for s, t in items]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestDeduplicateSentences(unittest.TestCase):

    def test_no_duplicates_returned_as_is(self):
        pairs = _pairs(("Jeg læser.", "I read."), ("Du skriver.", "You write."))
        result = _deduplicate(pairs)
        self.assertEqual(len(result), 2)

    def test_exact_duplicates_removed(self):
        pairs = _pairs(("Jeg læser.", "I read."), ("Jeg læser.", "I read."))
        result = _deduplicate(pairs)
        self.assertEqual(len(result), 1)

    def test_case_insensitive_on_sentence(self):
        pairs = _pairs(("Jeg læser.", "I read."), ("jeg læser.", "I read."))
        result = _deduplicate(pairs)
        self.assertEqual(len(result), 1)

    def test_empty_list_returns_empty(self):
        self.assertEqual(_deduplicate([]), [])


class TestExtractSentences(unittest.TestCase):

    def _make_agent(self, results):
        """results: list of (list[_SentencePair] | Exception), one per chunk."""
        call_idx = [0]

        async def fake_extract(chunk):
            idx = call_idx[0]
            call_idx[0] += 1
            value = results[idx]
            if isinstance(value, Exception):
                raise value
            mock_result = MagicMock()
            mock_result.sentences = value
            return mock_result

        agent = MagicMock()
        agent.extract = fake_extract
        return agent

    @patch("dlg.sentence_extractor.SentenceExtractionAgent")
    def test_single_chunk_success(self, MockAgent):
        sentences = _pairs(("Jeg læser.", "I read."))
        MockAgent.return_value = self._make_agent([sentences])

        result, all_failed = run(extract_sentences(["some text"], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(len(result), 1)

    @patch("dlg.sentence_extractor.SentenceExtractionAgent")
    def test_deduplication_across_chunks(self, MockAgent):
        chunk1 = _pairs(("Jeg læser.", "I read."))
        chunk2 = _pairs(("Jeg læser.", "I read."), ("Du skriver.", "You write."))
        MockAgent.return_value = self._make_agent([chunk1, chunk2])

        result, all_failed = run(extract_sentences(["c1", "c2"], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(len(result), 2)

    @patch("dlg.sentence_extractor.SentenceExtractionAgent")
    def test_all_chunks_fail_sets_all_failed(self, MockAgent):
        MockAgent.return_value = self._make_agent([RuntimeError("LLM error")])

        result, all_failed = run(extract_sentences(["chunk1"], "danish", object()))

        self.assertTrue(all_failed)
        self.assertEqual(result, [])

    @patch("dlg.sentence_extractor.SentenceExtractionAgent")
    def test_partial_failure_continues(self, MockAgent):
        fail = RuntimeError("LLM error")
        success = _pairs(("Jeg læser.", "I read."))
        MockAgent.return_value = self._make_agent([fail, success])

        result, all_failed = run(extract_sentences(["c1", "c2"], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(len(result), 1)

    @patch("dlg.sentence_extractor.SentenceExtractionAgent")
    def test_empty_chunks_returns_empty_not_all_failed(self, MockAgent):
        MockAgent.return_value = MagicMock()

        result, all_failed = run(extract_sentences([], "danish", object()))

        self.assertFalse(all_failed)
        self.assertEqual(result, [])


class TestVerifySentences(unittest.TestCase):

    @patch("dlg.sentence_extractor.SentenceVerificationAgent")
    def test_returns_verified_subset(self, MockAgent):
        sentences = _pairs(("Jeg læser.", "I read."), ("bad", "bad"))
        verified = [sentences[0]]

        async def fake_verify(items):
            return verified

        agent = MagicMock()
        agent.verify_extracted = fake_verify
        MockAgent.return_value = agent

        result = run(verify_sentences(sentences, object()))
        self.assertEqual(result, verified)

    @patch("dlg.sentence_extractor.SentenceVerificationAgent")
    def test_returns_original_on_verification_failure(self, MockAgent):
        sentences = _pairs(("Jeg læser.", "I read."))

        async def fake_verify(items):
            raise RuntimeError("Verification service down")

        agent = MagicMock()
        agent.verify_extracted = fake_verify
        MockAgent.return_value = agent

        result = run(verify_sentences(sentences, object()))
        self.assertEqual(result, sentences)

    @patch("dlg.sentence_extractor.SentenceVerificationAgent")
    def test_empty_input_skips_verification(self, MockAgent):
        result = run(verify_sentences([], object()))
        MockAgent.assert_not_called()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
