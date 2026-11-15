from pathlib import Path

from ai_video_factory.theme import resolve_theme


def test_channel_theme_loads_and_contains_editorial_branding():
    root = Path(__file__).resolve().parents[1]
    theme = resolve_theme(
        "politics-of-everything",
        root / "config" / "themes" / "politics-of-everything.json",
    )
    assert theme.name == "politics-of-everything"
    assert theme.channel_name == "Politics of Everything"
    assert "systems" in theme.outro_caption.lower()
    assert "power" in theme.thumbnail_power_words
