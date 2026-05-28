from src.image_loader import _svg_text_with_fallback_font


def test_svg_text_with_fallback_font_rewrites_generic_font_family():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" font-family="-apple-system">'
        '<text x="0" y="20">中文标题</text></svg>'
    )

    result = _svg_text_with_fallback_font(svg)

    assert "-apple-system" not in result
    assert "PingFang SC" in result
    assert "中文标题" in result
