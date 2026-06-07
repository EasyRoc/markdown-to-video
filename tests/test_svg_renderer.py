import pytest
from pathlib import Path
from PIL import Image
from src.svg_renderer import render_svg_to_png, inject_cjk_font


class TestInjectCJKFont:
    def test_adds_font_to_svg_tag(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"></svg>'
        result = inject_cjk_font(svg)
        assert 'font-family="PingFang SC' in result

    def test_replaces_existing_font_family(self):
        svg = '<svg font-family="Arial" viewBox="0 0 100 100"><text>hello</text></svg>'
        result = inject_cjk_font(svg)
        assert 'font-family="Arial"' not in result
        assert "PingFang SC" in result


class TestRenderSvgToPng:
    def test_renders_simple_svg(self, tmp_path):
        svg_code = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">
            <rect width="200" height="100" fill="#4A90D9"/>
            <text x="100" y="55" text-anchor="middle" fill="white" font-size="16">Test</text>
        </svg>'''
        output = tmp_path / "test.png"
        render_svg_to_png(svg_code, str(output))
        assert output.exists()
        img = Image.open(output)
        assert img.size == (200, 100)

    def test_raises_on_broken_svg(self, tmp_path):
        output = tmp_path / "broken.png"
        with pytest.raises(Exception):
            render_svg_to_png("not svg at all <<<", str(output))
