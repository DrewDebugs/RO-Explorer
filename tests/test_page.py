"""M7 page checks: every figure in the factual sections is cited, links resolve,
and the pinned library versions agree across files."""

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "assets" / "app.js").read_text(encoding="utf-8")


class Blocks(HTMLParser):
    """Collect the text of <p>, <li> and <tr> blocks inside given section ids,
    together with whether the block contains a citation link."""

    BLOCK = {"p", "li", "tr"}

    def __init__(self, sections):
        super().__init__()
        self.sections, self.stack, self.current, self.blocks = sections, [], None, []
        self.in_section = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            self.in_section = a.get("id") if a.get("id") in self.sections else None
        if not self.in_section:
            return
        if tag in ("script", "style") or "eq" in (a.get("class") or "").split():
            self.skip += 1
        if tag in self.BLOCK and self.current is None:
            self.current = {"tag": tag, "text": "", "cited": False, "section": self.in_section, "depth": 0}
        if self.current is not None:
            if tag == self.current["tag"]:
                self.current["depth"] += 1
            if tag == "a" and "cite" in (a.get("class") or ""):
                self.current["cited"] = True

    def handle_endtag(self, tag):
        if tag == "section":
            self.in_section = None
        if self.skip and tag in ("script", "style", "div"):
            self.skip = max(0, self.skip - 1) if tag != "div" else self.skip
        if self.current is not None and tag == self.current["tag"]:
            self.current["depth"] -= 1
            if self.current["depth"] == 0:
                self.blocks.append(self.current)
                self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data


def test_every_figure_in_factual_sections_is_cited():
    """Plan M7: no uncited number in the industry and economics text."""
    parser = Blocks({"industry", "economics"})
    parser.feed(HTML)
    # numbers that are definitions or derived from the model rather than facts
    allowed = re.compile(r"^\s*$")
    bad = []
    for b in parser.blocks:
        text = re.sub(r"\\\(.*?\\\)", "", b["text"])  # inline math is notation, not data
        text = re.sub(r"§\s*\d+(\.\d+)?|\[\d+\]", "", text)  # section refs, citation markers
        if re.search(r"\d", text) and not b["cited"] and not allowed.match(text):
            bad.append(f"{b['section']}: {' '.join(text.split())[:100]}")
    assert not bad, "uncited figures:\n" + "\n".join(bad)


def test_citations_resolve_and_every_reference_is_used():
    cited = set(re.findall(r'class="cite" href="#(ref-[\w-]+)"', HTML))
    defined = set(re.findall(r'<li id="(ref-[\w-]+)"', HTML))
    assert cited <= defined, f"citations without a reference: {cited - defined}"
    assert defined <= cited, f"references never cited: {defined - cited}"


def test_internal_anchors_exist():
    ids = set(re.findall(r'id="([\w-]+)"', HTML))
    for target in re.findall(r'href="#([\w-]+)"', HTML):
        assert target in ids, target


def test_pinned_versions_agree():
    smoke = (ROOT / "tests" / "test_smoke.py").read_text()
    req = (ROOT / "requirements-dev.txt").read_text()
    pyodide = re.search(r'PYODIDE_VERSION = "([\d.]+)"', APP).group(1)
    assert f"/pyodide/v{pyodide}/full/pyodide.js" in HTML
    assert f"Pyodide</a> {pyodide}" in HTML  # credits
    numpy = re.search(r'PYODIDE_NUMPY = "([\d.]+)"', smoke).group(1)
    assert f"numpy=={numpy}" in req and f"NumPy</a> {numpy}" in HTML
    katex = set(re.findall(r"katex@([\d.]+)", HTML))
    plotly = set(re.findall(r"plotly\.js-dist-min@([\d.]+)", HTML))
    assert len(katex) == 1 and len(plotly) == 1
    assert f"KaTeX</a> {katex.pop()}" in HTML and f"Plotly.js</a> {plotly.pop()}" in HTML


def test_external_scripts_are_pinned():
    for src in re.findall(r'<script[^>]+src="(https://[^"]+)"', HTML):
        assert re.search(r"@\d+\.\d+\.\d+|/v\d+\.\d+\.\d+/", src), src


def test_citation_numbers_match_reference_order():
    order = re.findall(r'<li id="(ref-[\w-]+)"', HTML)
    for ref, num in re.findall(r'class="cite" href="#(ref-[\w-]+)">\[(\d+)\]', HTML):
        assert order.index(ref) + 1 == int(num), f"{ref} is cited as [{num}] but is item {order.index(ref) + 1}"
