from server.ai_radar_api.verification import score_authority, verify_from_page_text


def test_official_source_scores_high():
    result = score_authority(
        item={"site_name": "Official AI Updates", "source": "OpenAI News", "url": "https://openai.com/news/test"},
        page_text="OpenAI announced a new API update in its official changelog.",
        evidence_links=["https://openai.com/news/test"],
        deep=False,
    )
    assert result["authority_score"] >= 85
    assert result["status"] == "verified"


def test_third_party_with_primary_links_scores_medium_high():
    result = score_authority(
        item={"site_name": "Example Blog", "source": "AI", "url": "https://blog.example/a"},
        page_text="This report cites the OpenAI announcement and GitHub release.",
        evidence_links=["https://openai.com/news/a", "https://github.com/org/repo/releases/tag/v1"],
        deep=False,
    )
    assert 70 <= result["authority_score"] <= 84


def test_summary_without_evidence_scores_low():
    result = score_authority(
        item={"site_name": "Aggregator", "source": "Hot", "url": "https://example.com/a"},
        page_text="People say a new model may be coming soon.",
        evidence_links=[],
        deep=False,
    )
    assert result["authority_score"] < 50


def test_verify_from_page_text_extracts_primary_links():
    result = verify_from_page_text(
        {"title": "A", "url": "https://example.com/a"},
        '<a href="https://openai.com/news/a">official post</a>',
        deep=False,
    )
    assert "https://openai.com/news/a" in result["evidence_links"]
