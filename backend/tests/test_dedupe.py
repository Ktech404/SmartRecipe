from app.providers.base import RawRecipe
from app.services.dedupe import content_hash, dedupe_by_url, normalize_url


def test_lowercases_host_and_upgrades_http():
    assert normalize_url("HTTP://Example.COM/Recipe") == "https://example.com/Recipe"


def test_drops_www_fragment_and_default_port():
    assert normalize_url("https://www.example.com:443/a#steps") == "https://example.com/a"


def test_keeps_non_default_port():
    assert normalize_url("http://example.com:8080/a") == "https://example.com:8080/a"


def test_drops_tracking_params_and_sorts_the_rest():
    url = "https://example.com/r?utm_source=x&b=2&fbclid=abc&a=1"
    assert normalize_url(url) == "https://example.com/r?a=1&b=2"


def test_trailing_slash_dropped_but_root_kept():
    assert normalize_url("https://example.com/r/") == "https://example.com/r"
    assert normalize_url("https://example.com") == "https://example.com/"


def test_comment_links_are_the_same_page():
    base = "https://blog.example.com/2009/12/post.html"
    a = normalize_url(base + "?showComment=1262245863035")
    b = normalize_url(base + "?replytocom=801")
    assert a == b == normalize_url(base)


def test_same_page_different_forms_match():
    a = normalize_url("http://www.example.com/pasta/?utm_medium=email")
    b = normalize_url("https://example.com/pasta#top")
    assert a == b


def test_unusable_urls_return_none():
    for bad in [None, "", "   ", "ftp://example.com/a", "not a url", "javascript:alert(1)"]:
        assert normalize_url(bad) is None


def test_hash_ignores_case_punctuation_and_ingredient_order():
    a = content_hash("Garlic Pasta!", ["2 cloves garlic, minced", "200g pasta"])
    b = content_hash("garlic pasta", ["200G PASTA", "2 cloves garlic minced"])
    assert a == b and len(a) == 64


def test_hash_differs_for_different_recipes():
    a = content_hash("Garlic Pasta", ["200g pasta", "garlic"])
    b = content_hash("Garlic Pasta", ["200g pasta", "garlic", "chili flakes"])
    assert a != b


def test_hash_is_none_without_title_or_ingredients():
    assert content_hash("", ["rice"]) is None
    assert content_hash(None, ["rice"]) is None
    assert content_hash("Plain rice", []) is None
    assert content_hash("Plain rice", ["", "  "]) is None


def test_dedupe_by_url_keeps_first_and_order():
    def r(url, title):
        return RawRecipe(source_url=url, title=title)

    recipes = [
        r("https://www.example.com/a?utm_source=x", "A"),
        r("https://other.com/b", "B"),
        r("http://example.com/a/", "A again"),
        r("not a url", "Broken"),
    ]
    kept = dedupe_by_url(recipes, lambda x: x.source_url)
    assert [x.title for x in kept] == ["A", "B"]


def test_more_click_ids_are_dropped_but_real_parameters_stay():
    url = "https://example.com/r?id=42&gbraid=x&_hsenc=y&mkt_tok=z&ttclid=q&_ga=1"
    assert normalize_url(url) == normalize_url("https://example.com/r?id=42")
    assert normalize_url(url) != normalize_url("https://example.com/r?id=43")
