"""Unit tests for the consolidated Shield redactor (P7.1, spec 08 §2.4)."""

from __future__ import annotations

import pytest

from korchestrator.security import Shield


@pytest.mark.parametrize(
    ("text", "token", "kind"),
    [
        ("email me at alice@example.com please", "[MASKED_EMAIL]", "EMAIL"),
        ("card 4111 1111 1111 1111 on file", "[MASKED_PAN]", "PAN"),
        ("ssn 123-45-6789 recorded", "[MASKED_SSN]", "SSN"),
        ("iban GB82WEST12345698765432 ok", "[MASKED_IBAN]", "IBAN"),
        ("ring +1 415 555 2671 today", "[MASKED_PHONE]", "PHONE"),
        ("token sk-abcdEFGH1234abcdEFGH1234 leaked", "[MASKED_SECRET]", "SECRET"),
        ("aws AKIAIOSFODNN7EXAMPLE key", "[MASKED_SECRET]", "SECRET"),
        ("auth Bearer abcdef1234567890xyz here", "[MASKED_SECRET]", "SECRET"),
    ],
)
def test_each_entity_is_masked(text: str, token: str, kind: str) -> None:
    result = Shield().redact(text)
    assert token in result.text
    assert result.redacted is True
    assert kind in result.types


def test_pan_must_pass_luhn() -> None:
    # A 16-digit run that fails the Luhn check is not a card number and is left alone by default.
    result = Shield().redact("ref 4111 1111 1111 1112 end")
    assert "[MASKED_PAN]" not in result.text
    assert result.redacted is False


def test_high_sensitivity_fails_toward_masking() -> None:
    # Ambiguous long digit runs are masked even without a valid Luhn checksum.
    result = Shield(high_sensitivity=True).redact("ref 4111 1111 1111 1112 end")
    assert "[MASKED_PAN]" in result.text


def test_clean_text_is_untouched() -> None:
    result = Shield().redact("the quarterly report has three sections")
    assert result.redacted is False
    assert result.types == ()
    assert result.text == "the quarterly report has three sections"


def test_multiple_entities_in_one_string() -> None:
    result = Shield().redact("mail a@b.com card 4111111111111111 ssn 123-45-6789")
    assert result.text == "mail [MASKED_EMAIL] card [MASKED_PAN] ssn [MASKED_SSN]"
    assert set(result.types) == {"EMAIL", "PAN", "SSN"}


def test_redact_value_walks_json_structures() -> None:
    payload = {"user": {"email": "x@y.com"}, "notes": ["call +1 415 555 2671", "clean"]}
    masked, changed = Shield().redact_value(payload)
    assert changed is True
    assert masked == {
        "user": {"email": "[MASKED_EMAIL]"},
        "notes": ["call [MASKED_PHONE]", "clean"],
    }


def test_redact_value_leaves_non_strings_and_reports_no_change() -> None:
    masked, changed = Shield().redact_value({"count": 3, "ok": True, "empty": None})
    assert changed is False
    assert masked == {"count": 3, "ok": True, "empty": None}
