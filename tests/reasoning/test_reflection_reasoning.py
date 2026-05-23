"""
Tests for ReflectionReasoning engine.
Covers: init, _perform_reasoning, _generate_initial_answer, _critique_answer,
_evaluate_quality, _refine_answer, _parse_quality_score, _format_context,
_build_*_prompt methods, get_metadata, and the inherited reason() entry point.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.reasoning.reflection_reasoning import ReflectionReasoning
from app.reasoning.types import ReasoningStatus


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def make_response(content: str) -> MagicMock:
    r = MagicMock()
    r.content = content
    return r


@pytest.fixture
def mock_model():
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value=make_response("default response"))
    return provider


@pytest.fixture
def engine(mock_model):
    return ReflectionReasoning(mock_model, {
        "max_iterations": 3,
        "quality_threshold": 0.8,
        "critique_temperature": 0.3,
        "refinement_temperature": 0.7,
    })


@pytest.fixture
def engine_1iter(mock_model):
    return ReflectionReasoning(mock_model, {"max_iterations": 1, "quality_threshold": 0.9})


@pytest.fixture
def engine_2iter(mock_model):
    return ReflectionReasoning(mock_model, {"max_iterations": 2, "quality_threshold": 1.0})


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_defaults(self, mock_model):
        e = ReflectionReasoning(mock_model)
        assert e.max_iterations == 3
        assert e.quality_threshold == 0.8
        assert e.critique_temp == 0.3
        assert e.refinement_temp == 0.7

    def test_custom_config(self, mock_model):
        e = ReflectionReasoning(mock_model, {
            "max_iterations": 5,
            "quality_threshold": 0.95,
            "critique_temperature": 0.1,
            "refinement_temperature": 0.9,
        })
        assert e.max_iterations == 5
        assert e.quality_threshold == 0.95
        assert e.critique_temp == 0.1
        assert e.refinement_temp == 0.9

    def test_none_config_uses_defaults(self, mock_model):
        e = ReflectionReasoning(mock_model, None)
        assert e.max_iterations == 3

    def test_metadata_type(self, engine):
        assert engine._metadata["type"] == "ReflectionReasoning"

    def test_metadata_version(self, engine):
        assert engine._metadata["version"] == "1.0.0"

    def test_metadata_stores_config(self, mock_model):
        cfg = {"max_iterations": 2}
        e = ReflectionReasoning(mock_model, cfg)
        assert e._metadata["config"] == cfg

    def test_model_stored(self, mock_model):
        e = ReflectionReasoning(mock_model)
        assert e.model is mock_model


# ---------------------------------------------------------------------------
# _generate_initial_answer
# ---------------------------------------------------------------------------

class TestGenerateInitialAnswer:
    @pytest.mark.asyncio
    async def test_returns_model_content(self, engine, mock_model):
        mock_model.generate.return_value = make_response("Initial answer")
        result = await engine._generate_initial_answer("Q", {})
        assert result == "Initial answer"

    @pytest.mark.asyncio
    async def test_calls_generate_with_refinement_temp(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {})
        mock_model.generate.assert_called_once()
        assert mock_model.generate.call_args.kwargs["temperature"] == engine.refinement_temp

    @pytest.mark.asyncio
    async def test_records_generate_step(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {})
        assert len(engine._steps) == 1
        assert engine._steps[0]["action"] == "generate"
        assert engine._steps[0]["step_number"] == 1

    @pytest.mark.asyncio
    async def test_step_status_completed(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {})
        assert engine._steps[0]["status"] == ReasoningStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_prompt_contains_query(self, engine, mock_model):
        await engine._generate_initial_answer("my unique query", {})
        prompt_used = mock_model.generate.call_args.kwargs["prompt"]
        assert "my unique query" in prompt_used

    @pytest.mark.asyncio
    async def test_prompt_contains_context(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {"topic": "science"})
        prompt_used = mock_model.generate.call_args.kwargs["prompt"]
        assert "science" in prompt_used

    @pytest.mark.asyncio
    async def test_empty_context_no_context_section(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {})
        prompt_used = mock_model.generate.call_args.kwargs["prompt"]
        assert "Контекст" not in prompt_used


# ---------------------------------------------------------------------------
# _critique_answer
# ---------------------------------------------------------------------------

class TestCritiqueAnswer:
    @pytest.mark.asyncio
    async def test_returns_critique_content(self, engine, mock_model):
        mock_model.generate.return_value = make_response("needs improvement")
        result = await engine._critique_answer("Q", "A", {}, 0)
        assert result == "needs improvement"

    @pytest.mark.asyncio
    async def test_uses_critique_temperature(self, engine, mock_model):
        await engine._critique_answer("Q", "A", {}, 0)
        assert mock_model.generate.call_args.kwargs["temperature"] == engine.critique_temp

    @pytest.mark.asyncio
    async def test_records_critique_step(self, engine, mock_model):
        await engine._critique_answer("Q", "A", {}, 0)
        steps = [s for s in engine._steps if s["action"] == "critique"]
        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_step_description_has_iteration(self, engine, mock_model):
        await engine._critique_answer("Q", "A", {}, 2)
        step = next(s for s in engine._steps if s["action"] == "critique")
        assert "iteration 3" in step["description"]

    @pytest.mark.asyncio
    async def test_prompt_contains_query_and_answer(self, engine, mock_model):
        await engine._critique_answer("my question", "my answer", {}, 0)
        prompt = mock_model.generate.call_args.kwargs["prompt"]
        assert "my question" in prompt
        assert "my answer" in prompt

    @pytest.mark.asyncio
    async def test_answer_truncated_in_action_input(self, engine, mock_model):
        long_answer = "x" * 300
        await engine._critique_answer("Q", long_answer, {}, 0)
        step = next(s for s in engine._steps if s["action"] == "critique")
        assert len(step["action_input"]["answer"]) <= 203  # 200 + "..."


# ---------------------------------------------------------------------------
# _evaluate_quality
# ---------------------------------------------------------------------------

class TestEvaluateQuality:
    @pytest.mark.asyncio
    async def test_parses_decimal_score(self, engine, mock_model):
        mock_model.generate.return_value = make_response("0.75")
        score = await engine._evaluate_quality("Q", "A", "C", 0)
        assert score == 0.75

    @pytest.mark.asyncio
    async def test_uses_low_temperature(self, engine, mock_model):
        mock_model.generate.return_value = make_response("0.5")
        await engine._evaluate_quality("Q", "A", "C", 0)
        assert mock_model.generate.call_args.kwargs["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_records_evaluate_step(self, engine, mock_model):
        mock_model.generate.return_value = make_response("0.8")
        await engine._evaluate_quality("Q", "A", "C", 0)
        steps = [s for s in engine._steps if s["action"] == "evaluate"]
        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_step_metadata_has_quality_score(self, engine, mock_model):
        mock_model.generate.return_value = make_response("0.65")
        await engine._evaluate_quality("Q", "A", "C", 0)
        step = next(s for s in engine._steps if s["action"] == "evaluate")
        assert step["metadata"]["quality_score"] == 0.65

    @pytest.mark.asyncio
    async def test_invalid_response_defaults_to_half(self, engine, mock_model):
        mock_model.generate.return_value = make_response("no number here")
        score = await engine._evaluate_quality("Q", "A", "C", 0)
        assert score == 0.5

    @pytest.mark.asyncio
    async def test_step_description_has_iteration(self, engine, mock_model):
        mock_model.generate.return_value = make_response("0.7")
        await engine._evaluate_quality("Q", "A", "C", 1)
        step = next(s for s in engine._steps if s["action"] == "evaluate")
        assert "iteration 2" in step["description"]

    @pytest.mark.asyncio
    async def test_critique_truncated_in_action_input(self, engine, mock_model):
        mock_model.generate.return_value = make_response("0.5")
        long_critique = "c" * 300
        await engine._evaluate_quality("Q", "A", long_critique, 0)
        step = next(s for s in engine._steps if s["action"] == "evaluate")
        assert len(step["action_input"]["critique"]) <= 203


# ---------------------------------------------------------------------------
# _refine_answer
# ---------------------------------------------------------------------------

class TestRefineAnswer:
    @pytest.mark.asyncio
    async def test_returns_refined_content(self, engine, mock_model):
        mock_model.generate.return_value = make_response("refined answer")
        result = await engine._refine_answer("Q", "old", "critique", {}, 0)
        assert result == "refined answer"

    @pytest.mark.asyncio
    async def test_uses_refinement_temperature(self, engine, mock_model):
        await engine._refine_answer("Q", "A", "C", {}, 0)
        assert mock_model.generate.call_args.kwargs["temperature"] == engine.refinement_temp

    @pytest.mark.asyncio
    async def test_records_refine_step(self, engine, mock_model):
        await engine._refine_answer("Q", "A", "C", {}, 0)
        steps = [s for s in engine._steps if s["action"] == "refine"]
        assert len(steps) == 1

    @pytest.mark.asyncio
    async def test_step_description_has_iteration(self, engine, mock_model):
        await engine._refine_answer("Q", "A", "C", {}, 0)
        step = next(s for s in engine._steps if s["action"] == "refine")
        assert "iteration 1" in step["description"]

    @pytest.mark.asyncio
    async def test_prompt_contains_query_answer_critique(self, engine, mock_model):
        await engine._refine_answer("my q", "my a", "my c", {}, 0)
        prompt = mock_model.generate.call_args.kwargs["prompt"]
        assert "my q" in prompt
        assert "my a" in prompt
        assert "my c" in prompt

    @pytest.mark.asyncio
    async def test_step_status_completed(self, engine, mock_model):
        await engine._refine_answer("Q", "A", "C", {}, 0)
        step = next(s for s in engine._steps if s["action"] == "refine")
        assert step["status"] == ReasoningStatus.COMPLETED


# ---------------------------------------------------------------------------
# _parse_quality_score
# ---------------------------------------------------------------------------

class TestParseQualityScore:
    def test_decimal_0_75(self, engine):
        assert engine._parse_quality_score("0.75") == 0.75

    def test_decimal_0_0(self, engine):
        assert engine._parse_quality_score("0.0") == 0.0

    def test_decimal_1_0(self, engine):
        assert engine._parse_quality_score("1.0") == 1.0

    def test_integer_0(self, engine):
        assert engine._parse_quality_score("0") == 0.0

    def test_integer_1(self, engine):
        assert engine._parse_quality_score("1") == 1.0

    def test_score_embedded_in_text(self, engine):
        assert engine._parse_quality_score("The score is 0.85 out of 1.0") == 0.85

    def test_score_with_prefix(self, engine):
        assert engine._parse_quality_score("Score: 0.6") == 0.6

    def test_empty_string_returns_default(self, engine):
        assert engine._parse_quality_score("") == 0.5

    def test_no_number_returns_default(self, engine):
        assert engine._parse_quality_score("excellent quality") == 0.5

    def test_multiple_numbers_takes_first(self, engine):
        # regex finds first match
        result = engine._parse_quality_score("0.7 then 0.9")
        assert result == 0.7

    def test_clamp_stays_within_range(self, engine):
        # max(0, min(1, score)) — score extracted is always 0-1 by regex
        result = engine._parse_quality_score("0.99")
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# _format_context
# ---------------------------------------------------------------------------

class TestFormatContext:
    def test_simple_string_values(self, engine):
        out = engine._format_context({"a": "hello", "b": "world"})
        assert "a: hello" in out
        assert "b: world" in out

    def test_list_value_gets_ellipsis(self, engine):
        out = engine._format_context({"items": [1, 2, 3]})
        assert "items:" in out
        assert "..." in out

    def test_dict_value_gets_ellipsis(self, engine):
        out = engine._format_context({"nested": {"x": 1}})
        assert "nested:" in out
        assert "..." in out

    def test_empty_context_returns_empty_string(self, engine):
        assert engine._format_context({}) == ""

    def test_long_list_truncated(self, engine):
        big_list = list(range(1000))
        out = engine._format_context({"data": big_list})
        # The str(value)[:200] truncation means the line is bounded
        assert len(out) < 300

    def test_numeric_value(self, engine):
        out = engine._format_context({"count": 42})
        assert "count: 42" in out


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

class TestBuildInitialPrompt:
    def test_contains_query(self, engine):
        p = engine._build_initial_prompt("test query", {})
        assert "test query" in p

    def test_no_context_no_context_header(self, engine):
        p = engine._build_initial_prompt("Q", {})
        assert "Контекст" not in p

    def test_with_context_includes_context_header(self, engine):
        p = engine._build_initial_prompt("Q", {"key": "val"})
        assert "Контекст" in p
        assert "val" in p

    def test_contains_answer_prompt(self, engine):
        p = engine._build_initial_prompt("Q", {})
        assert "Ответь" in p


class TestBuildCritiquePrompt:
    def test_contains_query(self, engine):
        p = engine._build_critique_prompt("my q", "my a", {})
        assert "my q" in p

    def test_contains_answer(self, engine):
        p = engine._build_critique_prompt("Q", "my answer", {})
        assert "my answer" in p

    def test_contains_criteria(self, engine):
        p = engine._build_critique_prompt("Q", "A", {})
        assert "Точность" in p
        assert "Полнота" in p


class TestBuildEvaluationPrompt:
    def test_contains_all_three_inputs(self, engine):
        p = engine._build_evaluation_prompt("Q", "A", "C")
        assert "Q" in p
        assert "A" in p
        assert "C" in p

    def test_contains_scale_description(self, engine):
        p = engine._build_evaluation_prompt("Q", "A", "C")
        assert "0.0" in p
        assert "1.0" in p

    def test_instructs_number_only(self, engine):
        p = engine._build_evaluation_prompt("Q", "A", "C")
        assert "ТОЛЬКО" in p or "числом" in p


class TestBuildRefinementPrompt:
    def test_contains_query_answer_critique(self, engine):
        p = engine._build_refinement_prompt("Q", "A", "C", {})
        assert "Q" in p
        assert "A" in p
        assert "C" in p

    def test_contains_improvement_instruction(self, engine):
        p = engine._build_refinement_prompt("Q", "A", "C", {})
        assert "улучш" in p.lower()


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------

class TestGetMetadata:
    def test_engine_type(self, engine):
        assert engine.get_metadata()["engine_type"] == "reflection"

    def test_max_iterations(self, engine):
        assert engine.get_metadata()["max_iterations"] == 3

    def test_quality_threshold(self, engine):
        assert engine.get_metadata()["quality_threshold"] == 0.8

    def test_critique_temperature(self, engine):
        assert engine.get_metadata()["critique_temperature"] == 0.3

    def test_refinement_temperature(self, engine):
        assert engine.get_metadata()["refinement_temperature"] == 0.7

    def test_total_steps_zero_initially(self, engine):
        assert engine.get_metadata()["total_steps"] == 0

    @pytest.mark.asyncio
    async def test_total_steps_after_generate(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {})
        assert engine.get_metadata()["total_steps"] == 1


# ---------------------------------------------------------------------------
# _perform_reasoning  (the core loop)
# ---------------------------------------------------------------------------

class TestPerformReasoning:
    @pytest.mark.asyncio
    async def test_returns_initial_answer_when_quality_met_immediately(self, engine, mock_model):
        mock_model.generate.return_value = make_response("great answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine._perform_reasoning("Q", {})

        assert result == "great answer"

    @pytest.mark.asyncio
    async def test_stops_early_when_threshold_met(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")
        call_count = [0]

        async def quality_fn(*a, **kw):
            call_count[0] += 1
            return 0.9  # always above threshold

        with patch.object(engine, '_evaluate_quality', side_effect=quality_fn):
            await engine._perform_reasoning("Q", {})

        # Should stop after first iteration
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_runs_all_iterations_when_quality_never_met(self, engine_2iter, mock_model):
        mock_model.generate.return_value = make_response("answer")
        call_count = [0]

        async def low_quality(*a, **kw):
            call_count[0] += 1
            return 0.1  # always below threshold

        with patch.object(engine_2iter, '_evaluate_quality', side_effect=low_quality):
            await engine_2iter._perform_reasoning("Q", {})

        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_tracks_best_answer_by_quality(self, engine_2iter, mock_model):
        responses = ["answer A", "critique", "0.7", "answer B", "critique", "0.4", "refined"]
        idx = [0]

        def next_response(*a, **kw):
            r = make_response(responses[idx[0]])
            idx[0] = min(idx[0] + 1, len(responses) - 1)
            return r

        mock_model.generate.side_effect = next_response

        result = await engine_2iter._perform_reasoning("Q", {})
        # answer A had quality 0.7, answer B had 0.4 → best is answer A
        assert result == "answer A"

    @pytest.mark.asyncio
    async def test_no_refinement_on_last_iteration(self, engine_1iter, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def low_quality(*a, **kw):
            return 0.1

        with patch.object(engine_1iter, '_evaluate_quality', side_effect=low_quality):
            with patch.object(engine_1iter, '_refine_answer', new_callable=AsyncMock) as mock_refine:
                await engine_1iter._perform_reasoning("Q", {})
                # max_iterations=1, so last iteration is also first — no refine
                mock_refine.assert_not_called()

    @pytest.mark.asyncio
    async def test_refine_called_between_iterations(self, engine_2iter, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def low_quality(*a, **kw):
            return 0.1

        with patch.object(engine_2iter, '_evaluate_quality', side_effect=low_quality):
            with patch.object(engine_2iter, '_refine_answer', new_callable=AsyncMock,
                              return_value="refined") as mock_refine:
                await engine_2iter._perform_reasoning("Q", {})
                # 2 iterations, refine only between them (not on last)
                assert mock_refine.call_count == 1

    @pytest.mark.asyncio
    async def test_context_defaults_to_empty_dict(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            # Pass None as context — should not raise
            result = await engine._perform_reasoning("Q", None)

        assert result is not None

    @pytest.mark.asyncio
    async def test_generate_called_once_for_initial(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            await engine._perform_reasoning("Q", {})

        # At minimum: 1 generate (initial) + 1 critique = 2 calls
        assert mock_model.generate.call_count >= 2


# ---------------------------------------------------------------------------
# reason()  — the public entry point from BaseReasoning
# ---------------------------------------------------------------------------

class TestReasonPublicEntryPoint:
    @pytest.mark.asyncio
    async def test_reason_returns_result_dict(self, engine, mock_model):
        mock_model.generate.return_value = make_response("final answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("What is Python?")

        assert isinstance(result, dict)
        assert "answer" in result
        assert "steps" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_reason_status_completed_on_success(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q")

        assert result["status"] == ReasoningStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_reason_answer_is_string(self, engine, mock_model):
        mock_model.generate.return_value = make_response("my answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q")

        assert result["answer"] == "my answer"

    @pytest.mark.asyncio
    async def test_reason_steps_populated(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q")

        assert len(result["steps"]) > 0

    @pytest.mark.asyncio
    async def test_reason_resets_steps_between_calls(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            await engine.reason("Q1")
            result2 = await engine.reason("Q2")

        # Steps should only reflect the second call
        assert len(result2["steps"]) > 0
        # All step numbers should start from 1 (reset happened)
        step_numbers = [s["step_number"] for s in result2["steps"]]
        assert 1 in step_numbers

    @pytest.mark.asyncio
    async def test_reason_empty_query_raises_and_returns_failed(self, engine, mock_model):
        result = await engine.reason("")
        assert result["status"] == ReasoningStatus.FAILED
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_reason_model_exception_returns_failed(self, engine, mock_model):
        mock_model.generate.side_effect = RuntimeError("model down")
        result = await engine.reason("Q")
        assert result["status"] == ReasoningStatus.FAILED
        assert "model down" in result["error"]

    @pytest.mark.asyncio
    async def test_reason_includes_duration(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q")

        assert result["total_duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_reason_with_context(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q", context={"domain": "science"})

        assert result["status"] == ReasoningStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_reason_error_is_none_on_success(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q")

        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_reason_metadata_has_timestamp(self, engine, mock_model):
        mock_model.generate.return_value = make_response("answer")

        async def high_quality(*a, **kw):
            return 0.9

        with patch.object(engine, '_evaluate_quality', side_effect=high_quality):
            result = await engine.reason("Q")

        assert "timestamp" in result["metadata"]


# ---------------------------------------------------------------------------
# get_reasoning_steps (inherited)
# ---------------------------------------------------------------------------

class TestGetReasoningSteps:
    @pytest.mark.asyncio
    async def test_returns_steps_list(self, engine, mock_model):
        await engine._generate_initial_answer("Q", {})
        steps = engine.get_reasoning_steps()
        assert isinstance(steps, list)
        assert len(steps) == 1

    def test_empty_before_any_call(self, engine):
        assert engine.get_reasoning_steps() == []
