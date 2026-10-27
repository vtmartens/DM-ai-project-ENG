"""Static accessibility checks for the web client."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "frontend" / "styles.css"
INDEX = ROOT / "frontend" / "index.html"

TEXT_TOKENS = (
    "--text",
    "--text-muted",
    "--text-faint",
    "--accent-strong",
    "--success",
    "--info",
    "--danger",
)
BACKGROUND_TOKENS = ("--bg", "--bg-card", "--bg-input", "--bg-elevated")


def _luminance(hex_color):
    hex_color = hex_color.lstrip("#")
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    channels = [
        value / 12.92
        if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return (
        0.2126 * channels[0]
        + 0.7152 * channels[1]
        + 0.0722 * channels[2]
    )


def _contrast(first, second):
    first_lum = _luminance(first)
    second_lum = _luminance(second)
    brighter, darker = max(first_lum, second_lum), min(first_lum, second_lum)
    return (brighter + 0.05) / (darker + 0.05)


def _theme_tokens(block):
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})", block))


def _themes():
    css = STYLES.read_text(encoding="utf-8")
    dark = _theme_tokens(re.search(r":root\s*\{(.*?)\}", css, re.S).group(1))
    light = _theme_tokens(
        re.search(r':root\[data-theme="light"\]\s*\{(.*?)\}', css, re.S).group(1)
    )
    return {"dark": dark, "light": light}


def test_text_tokens_meet_wcag_aa_contrast():
    failures = []
    for theme_name, tokens in _themes().items():
        for foreground in TEXT_TOKENS:
            for background in BACKGROUND_TOKENS:
                ratio = _contrast(tokens[foreground], tokens[background])
                if ratio < 4.5:
                    failures.append(
                        f"{theme_name}: {foreground} on {background} = {ratio:.2f}"
                    )

    assert not failures, failures


def test_client_has_skip_links_and_landmarks():
    html = INDEX.read_text(encoding="utf-8")

    assert html.count('class="skip-link') == 2
    assert 'href="#main-content"' in html
    assert 'href="#command-input"' in html
    assert 'id="main-content"' in html
    assert 'tabindex="-1"' in html
    assert 'aria-label="Character, quests and inventory"' in html
    assert 'aria-label="Adventure"' in html
    assert 'role="log"' in html
    assert 'aria-label="NPC dialogue"' in html
    assert 'aria-label="Combat"' in html
    assert 'aria-label="Item details"' in html


def test_modals_expose_dialog_semantics():
    html = INDEX.read_text(encoding="utf-8")

    for modal_id in ("load-modal", "map-modal"):
        block = re.search(
            rf'<div id="{modal_id}"[^>]*>', html, re.S
        )
        assert block is not None
        tag = block.group(0)
        assert 'role="dialog"' in tag
        assert 'aria-modal="true"' in tag
        assert "aria-labelledby=" in tag
