"""Tests for HTML report rendering."""

from autogematria.research.html_report import render_full_report_html
from autogematria.research.name_report import build_name_report


class TestHtmlRendering:
    def test_basic_render(self):
        report = build_name_report("משה")
        html = render_full_report_html(report)
        assert "<!doctype html>" in html
        assert "משה" in html

    def test_contains_all_sections(self):
        report = build_name_report("אברהם")
        html = render_full_report_html(report)
        assert "Name Breakdown" in html
        assert "Gematria Across Methods" in html
        assert "Letter-by-Letter Analysis" in html
        assert "Kabbalistic Analysis" in html
        assert "Four Worlds" in html

    def test_multi_component_name(self):
        report = build_name_report("דוד בן שלמה כהן")
        html = render_full_report_html(report)
        assert "Father" in html
        assert "First Name" in html
        assert "Surname" in html

    def test_english_input_renders(self):
        report = build_name_report("Avraham ben Yitzchak")
        html = render_full_report_html(report)
        assert "אברהם" in html
        assert "יצחק" in html

    def test_gematria_values_present(self):
        report = build_name_report("משה")
        html = render_full_report_html(report)
        assert "345" in html

    def test_with_showcase_data(self):
        report = build_name_report("משה")
        mock_showcase = {
            "verdict_label": "Direct textual hit",
            "summary_line": "Found as a direct word",
            "headline_findings": [{
                "method": "SUBSTRING",
                "found_text": "משה",
                "explanation": "Direct match",
                "location": {"book": "Exodus", "chapter": 2, "verse": 10},
                "params": {"mode": "exact_word"},
                "verse_context": {"ref": "Exodus 2:10", "hebrew": "ותקרא שמו משה", "english": "She named him Moses"},
                "confidence": {"score": 0.95},
            }],
            "supporting_findings": [],
            "interesting_findings": [],
        }
        html = render_full_report_html(report, showcase=mock_showcase)
        assert "Direct textual hit" in html
        assert "Torah Encodings" in html

    def test_sefirah_displayed(self):
        report = build_name_report("משה")
        html = render_full_report_html(report)
        assert "Binah" in html  # 345 reduces to 3 = Binah

    def test_milui_displayed(self):
        report = build_name_report("אב")
        html = render_full_report_html(report)
        assert "Milui" in html

    def test_atbash_displayed(self):
        report = build_name_report("אב")
        html = render_full_report_html(report)
        assert "AtBash" in html


class TestRealisticNames:
    """End-to-end tests with names that real users would input."""

    def test_yosef_katz(self):
        report = build_name_report("יוסף כץ")
        html = render_full_report_html(report)
        assert len(html) > 5000
        assert "יוסף" in html
        assert "כץ" in html

    def test_english_full_name(self):
        report = build_name_report("Yehuda ben Shimon Cohen")
        html = render_full_report_html(report)
        assert len(html) > 5000

    def test_single_name(self):
        report = build_name_report("נח")
        html = render_full_report_html(report)
        assert "נח" in html

    def test_female_name_with_parents(self):
        report = build_name_report("שרה בת אברהם ורבקה")
        html = render_full_report_html(report)
        assert "שרה" in html
        assert "אברהם" in html
        assert "רבקה" in html
        assert "Mother" in html
