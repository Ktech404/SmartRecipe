import pytest

from app.providers.base import RawRecipe
from app.services import recipe_parser
from app.services.recipe_parser import (
    GeminiRecipeParser,
    GenerateResult,
    Outcome,
    ParsedRecipe,
    ParserError,
    ParserRateLimited,
    ParserTimeout,
    ParserUnavailable,
    _map_error,
)


def _raw(text="Garlic pasta. Ingredients: pasta, garlic."):
    return RawRecipe(
        source_url="https://example.com/r", title="Page title", source_name="example.com",
        page_text=text,
    )


class FakeGenerate:
    """Returns queued results one by one and remembers each call."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, prompt, max_output_tokens):
        self.calls.append((prompt, max_output_tokens))
        item = self.results.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _ok(**fields):
    base = dict(is_recipe=True, title="Garlic Pasta", ingredient_lines=["200 g pasta", "2 cloves garlic"],
                instructions=["Boil pasta.", "Add garlic."])
    base.update(fields)
    return GenerateResult(ParsedRecipe(**base), "STOP", 100, 50)


def _parser(*results):
    gen = FakeGenerate(*results)
    return GeminiRecipeParser(generate=gen, sleep=lambda seconds: None), gen


def test_full_recipe_is_filled_in():
    parser, gen = _parser(_ok(total_minutes=30, servings=4, cuisine="Italian"))
    result = parser.parse(_raw())
    r = result.recipe
    assert result.outcome is Outcome.FULL and result.usable
    assert r.title == "Garlic Pasta"
    assert r.ingredient_lines == ("200 g pasta", "2 cloves garlic")
    assert r.instructions == "Boil pasta.\nAdd garlic."
    assert (r.total_minutes, r.servings, r.cuisine) == (30, 4, "Italian")
    # fields we did not touch are kept
    assert r.source_url == "https://example.com/r" and r.source_name == "example.com"
    assert "Garlic pasta. Ingredients" in gen.calls[0][0]


def test_ingredients_without_steps_is_still_usable():
    parser, _ = _parser(_ok(instructions=[]))
    result = parser.parse(_raw())
    assert result.outcome is Outcome.INGREDIENTS_ONLY and result.usable
    assert result.recipe.instructions is None


def test_not_a_recipe_is_skipped():
    parser, _ = _parser(GenerateResult(ParsedRecipe(is_recipe=False)))
    result = parser.parse(_raw())
    assert result.outcome is Outcome.NOT_RECIPE
    assert result.recipe is None and not result.usable


def test_recipe_without_ingredients_is_skipped():
    parser, _ = _parser(_ok(ingredient_lines=["", "   "]))
    result = parser.parse(_raw())
    assert result.outcome is Outcome.NO_INGREDIENTS and result.recipe is None


def test_empty_page_text_never_calls_gemini():
    parser, gen = _parser()
    for text in (None, "", "   "):
        assert parser.parse(_raw(text)).outcome is Outcome.NO_TEXT
    assert gen.calls == []


def test_retries_once_with_bigger_limit_when_nothing_parsed():
    parser, gen = _parser(GenerateResult(None, "MAX_TOKENS"), _ok())
    result = parser.parse(_raw())
    assert result.usable
    assert [c[1] for c in gen.calls] == [4096, 8192]


def test_gives_up_after_one_retry():
    parser, gen = _parser(GenerateResult(None, "MAX_TOKENS"), GenerateResult(None, "MAX_TOKENS"))
    result = parser.parse(_raw())
    assert result.outcome is Outcome.NO_OUTPUT
    assert "MAX_TOKENS" in result.reason
    assert len(gen.calls) == 2


def test_title_falls_back_to_the_page_title():
    parser, _ = _parser(_ok(title="  "))
    assert parser.parse(_raw()).recipe.title == "Page title"


def test_lines_are_cleaned():
    parser, _ = _parser(_ok(ingredient_lines=["  2   cups\nrice ", "", "salt"]))
    assert parser.parse(_raw()).recipe.ingredient_lines == ("2 cups rice", "salt")


@pytest.mark.parametrize("servings,minutes", [(0, 0), (-3, -5), (5000, 99999)])
def test_implausible_numbers_are_dropped(servings, minutes):
    parser, _ = _parser(_ok(servings=servings, total_minutes=minutes))
    r = parser.parse(_raw()).recipe
    assert r.servings is None and r.total_minutes is None


def test_blank_cuisine_becomes_none():
    parser, _ = _parser(_ok(cuisine="  "))
    assert parser.parse(_raw()).recipe.cuisine is None


def test_page_text_is_capped_before_sending():
    parser, gen = _parser(_ok())
    parser.parse(_raw("x" * 50_000))
    assert len(gen.calls[0][0]) < recipe_parser.MAX_PAGE_CHARS + 2000


def test_prompt_tells_gemini_to_ignore_instructions_in_the_page():
    assert "untrusted" in recipe_parser.PROMPT
    assert "Never count ingredients" in recipe_parser.PROMPT


def test_tokens_are_added_up_including_retries():
    parser, _ = _parser(GenerateResult(None, "MAX_TOKENS", 10, 20), _ok())
    parser.parse(_raw())
    assert (parser.input_tokens, parser.output_tokens) == (110, 70)


def test_parser_errors_pass_through():
    parser, _ = _parser(ParserRateLimited("slow down"))
    with pytest.raises(ParserRateLimited):
        parser.parse(_raw())


def test_server_error_is_retried_then_succeeds():
    waits = []
    gen = FakeGenerate(ParserUnavailable("503"), _ok())
    parser = GeminiRecipeParser(generate=gen, sleep=waits.append)
    assert parser.parse(_raw()).usable
    assert waits == [2.0]
    assert len(gen.calls) == 2


def test_server_error_gives_up_after_two_retries():
    waits = []
    gen = FakeGenerate(*[ParserUnavailable("503")] * 3)
    parser = GeminiRecipeParser(generate=gen, sleep=waits.append)
    with pytest.raises(ParserUnavailable):
        parser.parse(_raw())
    assert waits == [2.0, 6.0]
    assert len(gen.calls) == 3


@pytest.mark.parametrize("error", [ParserRateLimited("429"), ParserTimeout("slow"), ParserError("x")])
def test_other_errors_are_not_retried(error):
    waits = []
    gen = FakeGenerate(error)
    parser = GeminiRecipeParser(generate=gen, sleep=waits.append)
    with pytest.raises(type(error)):
        parser.parse(_raw())
    assert waits == [] and len(gen.calls) == 1


def test_model_defaults_and_env_override(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert GeminiRecipeParser(generate=FakeGenerate()).model == "gemini-3.5-flash-lite"
    monkeypatch.setenv("GEMINI_MODEL", "other-model")
    assert GeminiRecipeParser(generate=FakeGenerate()).model == "other-model"
    assert GeminiRecipeParser(model="explicit", generate=FakeGenerate()).model == "explicit"


# ---- mapping SDK exceptions to our errors -------------------------------------


class _WithCode(Exception):
    def __init__(self, code):
        super().__init__("secret request detail")
        self.code = code


class DeadlineTimeout(Exception):
    pass


def test_429_maps_to_rate_limited():
    assert isinstance(_map_error(_WithCode(429)), ParserRateLimited)


def test_timeouts_map_to_parser_timeout():
    assert isinstance(_map_error(TimeoutError()), ParserTimeout)
    assert isinstance(_map_error(DeadlineTimeout()), ParserTimeout)


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_server_errors_map_to_unavailable(code):
    err = _map_error(_WithCode(code))
    assert isinstance(err, ParserUnavailable)
    assert "secret request detail" not in str(err)


def test_other_errors_map_to_parser_error_without_leaking_details():
    err = _map_error(_WithCode(400))
    assert type(err) is ParserError
    assert "secret request detail" not in str(err)


def test_prompt_asks_for_run_together_ingredients_to_be_split_but_not_prep_notes():
    assert "runs several separate ingredients together" in recipe_parser.PROMPT
    assert "own string" in recipe_parser.PROMPT
    assert "Do not split one" in recipe_parser.PROMPT
