import json
from html.parser import HTMLParser

from agentguard.report_viewer import SCRIPT, STYLE, csp_hash, render_viewer


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.scripts = []
        self.styles = []
        self.elements = []
        self.csp = None
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == "script":
            self.scripts.append("")
            self.current = self.scripts
        elif tag == "style":
            self.styles.append("")
            self.current = self.styles
        elif tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs["content"]

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.current = None

    def handle_data(self, text):
        if self.current is not None:
            self.current[-1] += text


def test_hostile_document_text_roundtrips_without_creating_active_html():
    attack = '</script><img src=x onerror="alert(1)"><script>alert(2)</script>\u2028&__SCRIPT__'
    report = {"episodes": [{"final_response": attack, "trace": [{"body": attack}]}]}
    page = Page(render_viewer(report, {"limits": [attack]}, {"task": attack}))
    assert len(page.scripts) == 2
    payload = json.loads(page.scripts[0])
    assert payload["episodes"] == report["episodes"]
    assert payload["tasks"]["task"] == attack
    assert page.scripts[1] == SCRIPT
    assert page.styles == [STYLE]
    assert not any(tag == "img" for tag, _ in page.elements)
    assert not any(name.startswith("on") for _, attrs in page.elements for name in attrs)


def test_viewer_csp_matches_exact_embedded_code_and_denies_network():
    page = Page(render_viewer({"episodes": []}, {}, {}))
    assert f"script-src 'sha256-{csp_hash(page.scripts[1])}'" in page.csp
    assert f"style-src 'sha256-{csp_hash(page.styles[0])}'" in page.csp
    assert "default-src 'none'" in page.csp
    assert "connect-src 'none'" in page.csp
    assert "'unsafe-inline'" not in page.csp
    assert not any("src" in attrs or "href" in attrs for _, attrs in page.elements)


def test_viewer_preserves_unicode_and_text_uses_safe_dom_apis():
    page = Page(render_viewer({"episodes": []}, {}, {"task": "Résumé · 東京 😀"}))
    assert json.loads(page.scripts[0])["tasks"]["task"] == "Résumé · 東京 😀"
    # Guard the intended trust boundary against future convenience substitutions.
    assert "innerHTML" not in SCRIPT
    assert "insertAdjacentHTML" not in SCRIPT
    assert "document.write" not in SCRIPT
    assert "textContent" in SCRIPT
