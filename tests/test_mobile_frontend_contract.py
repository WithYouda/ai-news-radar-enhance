from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mobile_nav_and_ask_entry_exist():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="mobileBottomNav"' in html
    assert 'data-view="today"' in html
    assert 'data-view="categories"' in html
    assert 'data-view="verification"' in html
    assert 'data-view="settings"' in html
    assert 'id="askAiButton"' in html


def test_mobile_css_is_scoped_to_small_screens():
    css = (ROOT / "assets/styles.css").read_text(encoding="utf-8")
    assert ".mobile-bottom-nav" in css
    assert "@media (max-width: 760px)" in css
    assert "padding-bottom" in css


def test_category_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'data-mobile-view="categories"' in html
    assert 'id="categoryView"' in html
    assert "loadTaxonomy" in js
    assert "renderCategoryView" in js


def test_verification_view_contract_exists():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "assets/app.js").read_text(encoding="utf-8")
    assert 'data-mobile-view="verification"' in html
    assert 'id="verificationView"' in html
    assert "loadVerificationSummary" in js
    assert "renderVerificationView" in js
    assert "deepVerifyItem" in js
