import pytest

from api.tests.conftest import schema_errors

Q = "Who fired the shots at Mainila?"
QUOTE_FIELDS = {"text", "gloss", "dist", "born", "died", "oldid_url"}


@pytest.fixture(scope="module")
def body(client):
    r = client.get("/api/ask", params={"q": Q})
    assert r.status_code == 200, r.text
    return r.json()


def test_quotes_for_every_edition(body):
    # PLAN B9 done check: quotes for every edition in seed-mini (edition order)
    assert not schema_errors("/api/ask", body)
    assert list(body["quotes"]) == ["fi", "sv", "de", "en", "ru", "et"]
    for lang, quotes in body["quotes"].items():
        assert len(quotes) == 3, lang
        assert [q["dist"] for q in quotes] == sorted(q["dist"] for q in quotes)
        assert all(q["oldid_url"].startswith(f"https://{lang}.wikipedia.org/w/index.php?oldid=") for q in quotes)


def test_nothing_but_quotes_and_glosses(body):
    assert set(body) == {"q", "as_of", "quotes", "sql"}
    for quotes in body["quotes"].values():
        for q in quotes:
            assert set(q) == QUOTE_FIELDS
    assert body["q"] == Q


def test_one_statement_as_of_with_the_vector_index(body):
    ask = [s for s in body["sql"] if "VEC_DISTANCE_COSINE" in s["text"]]
    assert len(ask) == 1
    assert "FOR SYSTEM_TIME AS OF" in ask[0]["text"] and ask[0]["index"] == "emb"


def test_as_of_only_quotes_sentences_alive_then(client):
    body = client.get("/api/ask", params={"q": Q, "as_of": "2009-06-01", "k": 5}).json()
    for quotes in body["quotes"].values():
        for q in quotes:
            assert q["born"] <= "2009-06-01" and (q["died"] is None or q["died"] > "2009-06-01")


def test_langs_k_and_errors(client):
    body = client.get("/api/ask", params={"q": Q, "langs": "fi,ru", "k": 1}).json()
    assert list(body["quotes"]) == ["fi", "ru"] and all(len(v) == 1 for v in body["quotes"].values())
    assert client.get("/api/ask", params={"q": "  "}).json()["error"]["code"] == "empty_question"
    assert client.get("/api/ask", params={"q": "x" * 501}).status_code == 422
    assert client.get("/api/ask").status_code == 422
