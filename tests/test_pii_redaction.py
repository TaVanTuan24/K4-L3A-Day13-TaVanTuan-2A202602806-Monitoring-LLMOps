from __future__ import annotations

from app.pii import scrub_text, scrub_value


def test_scrub_cccd() -> None:
    out = scrub_text("Số CCCD: 001234567890")
    assert "001234" not in out
    assert "REDACTED_CCCD" in out


def test_scrub_credit_card_separated_formats() -> None:
    for card in (
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111111111111111",
    ):
        out = scrub_text(f"Card: {card}")
        assert "4111" not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_nested_dict_and_list() -> None:
    value = {
        "user": {"email": "student@vinuni.edu.vn"},
        "notes": ["Call 090 123 4567", {"id": "001234567890"}],
        "card": ["4111 1111 1111 1111"],
    }
    out = scrub_value(value)
    rendered = str(out)
    assert "student@" not in rendered
    assert "090" not in rendered
    assert "001234" not in rendered
    assert "4111" not in rendered
    assert "REDACTED_EMAIL" in rendered
    assert "REDACTED_PHONE_VN" in rendered
    assert "REDACTED_CCCD" in rendered
    assert "REDACTED_CREDIT_CARD" in rendered


def test_scrub_value_preserves_non_string_scalars() -> None:
    value = {"count": 12, "ok": True, "score": 0.75, "none": None}
    out = scrub_value(value)
    assert out == value