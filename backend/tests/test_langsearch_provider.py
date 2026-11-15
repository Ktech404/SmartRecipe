import email.message
import urllib.error

import pytest

from app.providers import langsearch
from app.providers.base import (
    ProviderError,
    ProviderRateLimited,
    ProviderTimeout,
    RecipeSearchProvider,
    RecipeSearchQuery,
)
from app.providers.langsearch import LangSearchProvider, build_query_text


def _page(name="Garlic Pasta", url="https://www.example.com/garlic-pasta", text="Ingredients: pasta"):
    return {"name": name, "url": url, "text": text}


def _payload(pages, tokens=100):
    return {
        "code": 200,
        "data": {"webPages": {"value": pages}},
        "usage": {"input_tokens": 10, "output_tokens": tokens - 10},
    }


class FakePost:
    """Stands in for the HTTP call and remembers what it was sent."""

    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if self.error:
            raise self.error
        return self.payload


def _provider(post, **kwargs):
    return LangSearchProvider("test-key", post=post, **kwargs)


def test_is_a_recipe_search_provider():
    assert isinstance(_provider(FakePost(_payload([]))), RecipeSearchProvider)


def test_query_text_uses_ingredients_and_description():
    q = RecipeSearchQuery(ingredients=("chicken", "rice"), description="quick dinner")
    assert build_query_text(q) == "recipe with chicken rice quick dinner"
    assert build_query_text(RecipeSearchQuery(ingredients=())) == "recipe"


def test_sends_expected_request():
    post = FakePost(_payload([_page()]))
    _provider(post, max_chars=2000, timeout=12).search(
        RecipeSearchQuery(ingredients=("garlic",), limit=7)
    )
    url, headers, body, timeout = post.calls[0]
    assert url == langsearch.API_URL
    assert headers["Authorization"] == "Bearer test-key"
    assert body["query"] == "recipe with garlic"
    assert body["count"] == 7
    assert body["contents"] == {"text": {"maxCharacters": 2000}}
    assert timeout == 12


def test_count_is_capped_at_50():
    post = FakePost(_payload([]))
    _provider(post).search(RecipeSearchQuery(ingredients=("a",), limit=500))
    assert post.calls[0][2]["count"] == 50


def test_maps_pages_to_raw_recipes():
    post = FakePost(_payload([_page()]))
    [r] = _provider(post).search(RecipeSearchQuery(ingredients=("pasta",)))
    assert r.title == "Garlic Pasta"
    assert r.source_url == "https://www.example.com/garlic-pasta"
    assert r.source_name == "example.com"
    assert r.page_text == "Ingredients: pasta"
    assert r.ingredient_lines == () and r.instructions is None


def test_falls_back_to_snippet_when_no_text():
    page = {"name": "A", "url": "https://a.com/x", "snippet": "short excerpt"}
    [r] = _provider(FakePost(_payload([page]))).search(RecipeSearchQuery(ingredients=("a",)))
    assert r.page_text == "short excerpt"


def test_skips_incomplete_and_excluded_results():
    pages = [
        _page(url=""),
        _page(name=""),
        _page(text=""),
        _page(url="https://web.archive.org/web/2020/https://x.com/r"),
        _page(name="Keep", url="https://keep.com/r"),
    ]
    results = _provider(FakePost(_payload(pages))).search(RecipeSearchQuery(ingredients=("a",)))
    assert [r.title for r in results] == ["Keep"]


def test_result_count_never_exceeds_limit():
    pages = [_page(name=f"R{i}", url=f"https://s.com/{i}") for i in range(6)]
    results = _provider(FakePost(_payload(pages))).search(
        RecipeSearchQuery(ingredients=("a",), limit=3)
    )
    assert len(results) == 3


def test_empty_response_gives_empty_list():
    assert _provider(FakePost({"code": 200, "data": {}})).search(
        RecipeSearchQuery(ingredients=("a",))
    ) == []


def test_tokens_are_added_up():
    provider = _provider(FakePost(_payload([], tokens=300)))
    provider.search(RecipeSearchQuery(ingredients=("a",)))
    provider.search(RecipeSearchQuery(ingredients=("a",)))
    assert provider.tokens_used == 600


def test_error_code_in_payload_raises():
    with pytest.raises(ProviderError):
        _provider(FakePost({"code": 500, "msg": "boom"})).search(
            RecipeSearchQuery(ingredients=("a",))
        )


def test_provider_errors_pass_through():
    post = FakePost(error=ProviderTimeout("slow"))
    with pytest.raises(ProviderTimeout):
        _provider(post).search(RecipeSearchQuery(ingredients=("a",)))


def test_missing_key_is_rejected(monkeypatch):
    with pytest.raises(ValueError):
        LangSearchProvider("")
    monkeypatch.delenv("LANGSEARCH_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        LangSearchProvider.from_env()
    monkeypatch.setenv("LANGSEARCH_API_KEY", "abc")
    assert isinstance(LangSearchProvider.from_env(), LangSearchProvider)


# ---- the real HTTP function: failures become ProviderErrors ------------------


def _http_error(code, headers=None):
    msg = email.message.Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError("https://x", code, "err", msg, None)


def _call_with(monkeypatch, error):
    def fake_urlopen(request, timeout):
        raise error

    monkeypatch.setattr(langsearch.urllib.request, "urlopen", fake_urlopen)
    langsearch._post_json("https://x", {}, {}, 1.0)


def test_http_429_is_rate_limited_with_retry_after(monkeypatch):
    with pytest.raises(ProviderRateLimited) as err:
        _call_with(monkeypatch, _http_error(429, {"Retry-After": "7"}))
    assert err.value.retry_after == 7.0


def test_http_429_without_header(monkeypatch):
    with pytest.raises(ProviderRateLimited) as err:
        _call_with(monkeypatch, _http_error(429))
    assert err.value.retry_after is None


@pytest.mark.parametrize("code", [401, 403, 500, 503])
def test_other_http_errors_are_provider_errors(monkeypatch, code):
    with pytest.raises(ProviderError) as err:
        _call_with(monkeypatch, _http_error(code))
    assert not isinstance(err.value, (ProviderRateLimited, ProviderTimeout))


def test_timeouts_are_provider_timeouts(monkeypatch):
    with pytest.raises(ProviderTimeout):
        _call_with(monkeypatch, TimeoutError())
    with pytest.raises(ProviderTimeout):
        _call_with(monkeypatch, urllib.error.URLError(TimeoutError()))


def test_network_failure_is_a_provider_error(monkeypatch):
    with pytest.raises(ProviderError):
        _call_with(monkeypatch, urllib.error.URLError("name not resolved"))


def test_api_key_never_appears_in_error_messages(monkeypatch):
    provider = LangSearchProvider("super-secret-key")
    monkeypatch.setattr(
        langsearch.urllib.request,
        "urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(401)),
    )
    with pytest.raises(ProviderError) as err:
        provider.search(RecipeSearchQuery(ingredients=("a",)))
    assert "super-secret-key" not in str(err.value)
