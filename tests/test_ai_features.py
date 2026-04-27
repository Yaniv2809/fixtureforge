"""
Tests for FixtureForge v2.2.0 AI features.

All Groq API calls are mocked via unittest.mock — zero real API calls.
Run with:  pytest tests/test_ai_features.py -v
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from fixtureforge.ai.semantic_assert import (
    SemanticAssertionError,
    SemanticResult,
    _cosine_similarity,
    assert_semantic_match,
)
from fixtureforge.ai.failure_analyzer import SmartFailureAnalyzer


# ---------------------------------------------------------------------------
# assert_semantic_match — local mode (cosine similarity)
# ---------------------------------------------------------------------------

class TestCosimeSimilarity:
    def test_identical_strings_score_one(self):
        score = _cosine_similarity("the quick brown fox", "the quick brown fox")
        assert score == pytest.approx(1.0, abs=0.01)

    def test_unrelated_strings_score_low(self):
        score = _cosine_similarity("python testing library", "banana cake recipe")
        assert score < 0.3

    def test_empty_string_returns_zero(self):
        assert _cosine_similarity("", "some text") == 0.0
        assert _cosine_similarity("some text", "") == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        score = _cosine_similarity("great delivery fast shipping", "positive delivery experience")
        assert 0.0 < score < 1.0


class TestAssertSemanticMatchLocal:
    def test_pass_above_threshold(self):
        # Strings share words — cosine similarity will be > 0
        result = assert_semantic_match(
            actual="fast positive delivery experience overall",
            expected_intent="positive delivery experience",
            use_llm=False,
            threshold=0.5,
        )
        assert result.passed is True
        assert result.method == "local"
        assert 0.0 <= result.score <= 1.0

    def test_fail_below_threshold(self):
        result = assert_semantic_match(
            actual="I love cooking pasta with tomato sauce.",
            expected_intent="professional software engineering response",
            use_llm=False,
            threshold=0.99,
            raise_on_failure=False,
        )
        assert result.passed is False
        assert result.method == "local"

    def test_raises_semantic_assertion_error_on_failure(self):
        with pytest.raises(SemanticAssertionError) as exc_info:
            assert_semantic_match(
                actual="banana pancakes recipe",
                expected_intent="cloud infrastructure monitoring",
                use_llm=False,
                threshold=0.99,
                raise_on_failure=True,
            )
        err = exc_info.value
        assert isinstance(err, AssertionError)  # is a subclass of AssertionError
        assert err.result.passed is False
        assert "banana" in err.actual

    def test_returns_result_without_raising_when_flag_false(self):
        result = assert_semantic_match(
            actual="banana pancakes recipe",
            expected_intent="cloud infrastructure monitoring",
            use_llm=False,
            threshold=0.99,
            raise_on_failure=False,
        )
        assert isinstance(result, SemanticResult)
        assert result.passed is False

    def test_type_error_on_non_string_input(self):
        with pytest.raises(TypeError):
            assert_semantic_match(actual=123, expected_intent="some text")

    def test_semantic_result_str_representation(self):
        result = SemanticResult(passed=True, score=0.87, reason="good match", method="local")
        text = str(result)
        assert "PASS" in text
        assert "0.87" in text


# ---------------------------------------------------------------------------
# assert_semantic_match — LLM mode (Groq mocked)
# ---------------------------------------------------------------------------

class TestAssertSemanticMatchLLM:
    _MOCK_RESPONSE = json.dumps({
        "passed": True,
        "score": 0.91,
        "reason": "The actual output clearly conveys the expected positive intent.",
    })

    def test_llm_pass_uses_groq_response(self):
        with patch(
            "fixtureforge.ai.semantic_assert.groq_complete",
            return_value=self._MOCK_RESPONSE,
        ):
            result = assert_semantic_match(
                actual="This was a fantastic experience overall.",
                expected_intent="positive customer review",
                use_llm=True,
                threshold=0.8,
                api_key="mock-key",
            )
        assert result.passed is True
        assert result.score == pytest.approx(0.91)
        assert result.method == "llm"
        assert "positive" in result.reason

    def test_llm_fail_raises_error(self):
        fail_response = json.dumps({
            "passed": False,
            "score": 0.3,
            "reason": "Output does not match intent at all.",
        })
        with patch(
            "fixtureforge.ai.semantic_assert.groq_complete",
            return_value=fail_response,
        ):
            with pytest.raises(SemanticAssertionError):
                assert_semantic_match(
                    actual="totally unrelated text",
                    expected_intent="professional software response",
                    use_llm=True,
                    threshold=0.8,
                    api_key="mock-key",
                )

    def test_llm_fallback_to_local_on_parse_error(self):
        with patch(
            "fixtureforge.ai.semantic_assert.groq_complete",
            return_value="this is not valid json {{{{",
        ):
            result = assert_semantic_match(
                actual="quick brown fox",
                expected_intent="quick brown fox",
                use_llm=True,
                threshold=0.01,
                api_key="mock-key",
                raise_on_failure=False,
            )
        # Falls back to local — method reflects this
        assert result.method in ("local", "local_fallback")

    def test_llm_fallback_on_client_error(self):
        from fixtureforge.ai._groq_client import LLMClientError
        with patch(
            "fixtureforge.ai.semantic_assert.groq_complete",
            side_effect=LLMClientError("No API key"),
        ):
            result = assert_semantic_match(
                actual="quick fox",
                expected_intent="quick fox",
                use_llm=True,
                threshold=0.01,
                api_key=None,
                raise_on_failure=False,
            )
        assert result.method in ("local", "local_fallback")


# ---------------------------------------------------------------------------
# SmartFailureAnalyzer
# ---------------------------------------------------------------------------

class TestSmartFailureAnalyzer:
    def _make_report(self, failed: bool = True, when: str = "call") -> MagicMock:
        report = MagicMock()
        report.when = when
        report.failed = failed
        report.nodeid = "tests/test_example.py::test_something"
        report.longrepr = (
            "tests/test_example.py:42: AssertionError\n"
            "E   assert 1 == 2\n"
            "E   + where 1 = my_function()\n"
        )
        return report

    def test_does_not_trigger_on_setup_phase(self):
        analyzer = SmartFailureAnalyzer(api_key="mock-key")
        report = self._make_report(when="setup", failed=True)
        with patch.object(analyzer, "_analyze") as mock_analyze:
            analyzer.pytest_runtest_logreport(report)
            mock_analyze.assert_not_called()

    def test_does_not_trigger_on_passing_test(self):
        analyzer = SmartFailureAnalyzer(api_key="mock-key")
        report = self._make_report(failed=False, when="call")
        with patch.object(analyzer, "_analyze") as mock_analyze:
            analyzer.pytest_runtest_logreport(report)
            mock_analyze.assert_not_called()

    def test_skips_silently_without_api_key(self):
        analyzer = SmartFailureAnalyzer(api_key=None)
        report = self._make_report(failed=True, when="call")
        with patch.dict("os.environ", {}, clear=True):
            if "GROQ_API_KEY" in __import__("os").environ:
                pytest.skip("GROQ_API_KEY set in environment — skip no-key test")
            with patch.object(analyzer, "_analyze") as mock_analyze:
                analyzer.pytest_runtest_logreport(report)
                mock_analyze.assert_not_called()

    def test_does_not_change_report_passed_status(self):
        """Core guarantee: the plugin never modifies report state."""
        mock_groq_response = json.dumps({
            "explanation": "The assertion failed because values differ.",
            "likely_cause": "Function returns wrong value.",
            "suggested_fix": "Fix the return value in my_function().",
        })
        analyzer = SmartFailureAnalyzer(api_key="mock-key")
        report = self._make_report(failed=True, when="call")
        original_failed = report.failed

        with patch(
            "fixtureforge.ai.failure_analyzer.groq_complete",
            return_value=mock_groq_response,
        ):
            with patch("builtins.print"):  # suppress console output in tests
                analyzer._analyze(report, api_key="mock-key")

        # Report state must be unchanged
        assert report.failed == original_failed

    def test_analyze_counter_increments(self):
        mock_response = json.dumps({
            "explanation": "Values mismatch.",
            "likely_cause": "Off-by-one error.",
            "suggested_fix": "Check loop bounds.",
        })
        analyzer = SmartFailureAnalyzer(api_key="mock-key")
        report = self._make_report(failed=True, when="call")

        with patch(
            "fixtureforge.ai.failure_analyzer.groq_complete",
            return_value=mock_response,
        ):
            with patch("builtins.print"):
                analyzer._analyze(report, api_key="mock-key")

        assert analyzer._analyzed == 1

    def test_extract_failure_info_string_longrepr(self):
        analyzer = SmartFailureAnalyzer()
        report = MagicMock()
        report.nodeid = "tests/test_foo.py::test_bar"
        report.longrepr = "AssertionError: assert 1 == 2"
        info = analyzer._extract_failure_info(report)
        assert info["nodeid"] == "tests/test_foo.py::test_bar"
        assert "AssertionError" in info["tail"] or "AssertionError" in info["exc_type"]

    def test_groq_client_error_does_not_crash_session(self):
        from fixtureforge.ai._groq_client import LLMClientError
        analyzer = SmartFailureAnalyzer(api_key="mock-key")
        report = self._make_report(failed=True, when="call")

        with patch(
            "fixtureforge.ai.failure_analyzer.groq_complete",
            side_effect=LLMClientError("timeout"),
        ):
            # Must not raise — silently skips on error
            analyzer._analyze(report, api_key="mock-key")

        assert analyzer._analyzed == 0  # not counted — analysis failed
