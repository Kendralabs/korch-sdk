"""Leaf-utility layer (Shield). Imports: types, stdlib, pydantic.

The single consolidated PII/secret redactor (spec 08 §2.4). :class:`Shield` masks detected entities
to ``[MASKED_<TYPE>]`` — ``EMAIL``, ``SECRET``, ``IBAN``, ``SSN``, ``PAN`` (card numbers validated
by the Luhn checksum), and ``PHONE``. It runs on the ingest path before anything reaches
persistence, telemetry, logs, or an event subscriber. **There is exactly one redactor in the
package** — a second one anywhere is a review rejection.

High-sensitivity mode broadens masking (any 12-19 digit run is masked as a PAN even without a valid
Luhn checksum) so ambiguous data fails toward masking; the governance layer additionally *denies* a
high-sensitivity flow when the redactor is unavailable (fail-closed), wired in ``governance/``.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from korchestrator.types import JSONValue

__all__ = ["RedactionResult", "Shield"]


class RedactionResult(BaseModel):
    """The outcome of redacting one string."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    redacted: bool = False
    types: tuple[str, ...] = ()


# Detectors are applied in this order; earlier, more specific patterns win over later, broader ones
# (e.g. an SSN is masked before a bare digit run could be read as a phone number).
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b")
_AWS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_TOKEN = re.compile(r"\b(?:sk|rk|pk|ghp|xox[baprs])[-_][A-Za-z0-9\-_]{16,}\b")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}", re.IGNORECASE)
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# A 13-19 digit run, optionally grouped by single spaces or hyphens (candidate card number).
_PAN_CANDIDATE = re.compile(r"\b\d(?:[ \-]?\d){12,18}\b")
# International (+country) or grouped national phone numbers.
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().\-]{7,}\d(?![\w.])")


class Shield:
    """Mask PII and secrets in text (and JSON structures) to ``[MASKED_<TYPE>]`` tokens.

    Args:
        high_sensitivity: When ``True``, any 12-19 digit run is masked as a PAN even without a
            valid Luhn checksum, so ambiguous data fails toward masking.

    Example:
        >>> shield = Shield()
        >>> shield.redact("card 4111 1111 1111 1111 email a@b.com").text
        'card [MASKED_PAN] email [MASKED_EMAIL]'
        >>> shield.redact("nothing sensitive here").redacted
        False
    """

    def __init__(self, *, high_sensitivity: bool = False) -> None:
        """Configure the redactor's sensitivity."""
        self._high_sensitivity = high_sensitivity

    def redact(self, text: str) -> RedactionResult:
        """Mask every detected entity in ``text`` and report what was masked.

        Args:
            text: The untrusted text to sanitise.

        Returns:
            A :class:`RedactionResult` with the masked text, whether anything changed, and the
            set of entity types masked (sorted).

        Example:
            >>> Shield().redact("SSN 123-45-6789").text
            'SSN [MASKED_SSN]'
        """
        found: set[str] = set()

        def mask(kind: str) -> str:
            found.add(kind)
            return f"[MASKED_{kind}]"

        text = _EMAIL.sub(lambda _: mask("EMAIL"), text)
        for pattern in (_JWT, _AWS_KEY, _TOKEN, _BEARER):
            text = pattern.sub(lambda _: mask("SECRET"), text)
        text = _IBAN.sub(lambda _: mask("IBAN"), text)
        text = _SSN.sub(lambda _: mask("SSN"), text)
        text = _PAN_CANDIDATE.sub(lambda m: self._mask_pan(m.group(0), mask), text)
        text = _PHONE.sub(lambda m: _mask_phone(m.group(0), mask), text)

        return RedactionResult(text=text, redacted=bool(found), types=tuple(sorted(found)))

    def redact_value(self, value: JSONValue) -> tuple[JSONValue, bool]:
        """Recursively redact strings in a JSON value; return ``(redacted_value, changed)``.

        Matches the bridge's ``Redactor`` seam so :class:`Shield` can be injected directly.

        Example:
            >>> masked, changed = Shield().redact_value({"note": "call +1 415 555 2671"})
            >>> changed
            True
        """
        if isinstance(value, str):
            result = self.redact(value)
            return result.text, result.redacted
        if isinstance(value, Mapping):
            changed = False
            out: dict[str, JSONValue] = {}
            for key, item in value.items():
                out[key], item_changed = self.redact_value(item)
                changed = changed or item_changed
            return out, changed
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            changed = False
            items: list[JSONValue] = []
            for item in value:
                redacted_item, item_changed = self.redact_value(item)
                items.append(redacted_item)
                changed = changed or item_changed
            return items, changed
        return value, False

    def _mask_pan(self, candidate: str, mask: Callable[[str], str]) -> str:
        digits = re.sub(r"[ \-]", "", candidate)
        if _luhn_ok(digits) or self._high_sensitivity:
            return mask("PAN")
        return candidate


def _mask_phone(candidate: str, mask: Callable[[str], str]) -> str:
    # E.164 allows 7-15 digits; a longer run is not a phone number (e.g. a non-Luhn card-like run).
    digit_count = sum(character.isdigit() for character in candidate)
    if 7 <= digit_count <= 15:
        return mask("PHONE")
    return candidate


def _luhn_ok(digits: str) -> bool:
    """Return whether ``digits`` satisfies the Luhn checksum (a real card number does)."""
    if not digits.isdigit():
        return False
    total = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        value = int(digit)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
