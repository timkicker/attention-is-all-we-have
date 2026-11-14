from pipeline.l_scale import md_sentences


def test_markdown_article():
    md = (
        "# Talvisota\n\n**Talvisota** oli [Suomen](https://fi.wikipedia.org/wiki/Suomi) ja Neuvostoliiton "
        "välinen sota. Se alkoi 30. marraskuuta 1939 ja päättyi 13. maaliskuuta 1940.\n\n## Tausta\n\n"
        "- Luettelon kohta on tarpeeksi pitkä virkkeeksi.\n| taulukko | solu |\n"
    )
    out = md_sentences(md)
    assert out[0] == "Talvisota oli Suomen ja Neuvostoliiton välinen sota."
    assert "Se alkoi 30. marraskuuta 1939 ja päättyi 13. maaliskuuta 1940." in out
    assert "Luettelon kohta on tarpeeksi pitkä virkkeeksi." in out
    assert not any("#" in s or "|" in s or "](" in s for s in out)
