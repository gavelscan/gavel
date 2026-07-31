"""Verdict output contract for the judge.

Design decision (post-review): the model emits NO free-text that reaches
the feed. Everything a reader sees is rendered by the card layer from
our own deterministic strings and from a small closed set of enums. The
model's job is selection and classification, not prose:

- verdict            — PASS / FLAG / FAIL (clamped to the ceiling)
- key_findings       — a subset of the factsheet's finding names the
                       model is relying on (membership checked in the
                       judge; the model can only echo our trusted keys)
- hook_assessment    — closed enum
- currency_assessment— closed enum
- recipient_assessment — closed enum
- manipulation_detected — bool (coupled to the verdict in the judge)

This closes the whole class of "injection makes GAVEL publish attacker
copy": there is no attacker-influenced free text on the feed. Deny-lists
and digit gates become belt-and-suspenders for the card layer, not the
only thing standing between a hostile model and the feed.
"""

from typing import List, Tuple

VERDICTS = ("PASS", "FLAG", "FAIL")

HOOK_ASSESSMENTS = ("none", "benign", "suspicious", "hostile", "unknown")
CURRENCY_ASSESSMENTS = (
    "native_eth", "verified_official", "plausible",
    "unverified", "likely_impostor", "unknown",
)
RECIPIENT_ASSESSMENTS = ("contract", "established_eoa", "fresh_eoa", "unknown")

MAX_KEY_FINDINGS = 8

# JSON schema handed to the model provider's structured-output layer.
VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "key_findings": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": MAX_KEY_FINDINGS,
        },
        "hook_assessment": {"type": "string", "enum": list(HOOK_ASSESSMENTS)},
        "currency_assessment": {"type": "string", "enum": list(CURRENCY_ASSESSMENTS)},
        "recipient_assessment": {"type": "string", "enum": list(RECIPIENT_ASSESSMENTS)},
        "manipulation_detected": {"type": "boolean"},
    },
    "required": [
        "verdict", "key_findings", "hook_assessment",
        "currency_assessment", "recipient_assessment", "manipulation_detected",
    ],
    "additionalProperties": False,
}

_ENUM_FIELDS = {
    "verdict": VERDICTS,
    "hook_assessment": HOOK_ASSESSMENTS,
    "currency_assessment": CURRENCY_ASSESSMENTS,
    "recipient_assessment": RECIPIENT_ASSESSMENTS,
}


def validate_verdict(obj) -> Tuple[bool, List[str]]:
    """Structural validation, dependency-free. key_findings *membership*
    against the factsheet is checked in the judge, where the factsheet is
    available; here we only enforce shape and closed enums."""
    errors: List[str] = []
    if not isinstance(obj, dict):
        return False, ["output is not an object"]

    extra = set(obj) - set(VERDICT_SCHEMA["properties"])
    if extra:
        errors.append("unexpected keys: %s" % sorted(extra))
    for key in VERDICT_SCHEMA["required"]:
        if key not in obj:
            errors.append("missing key: %s" % key)
    if errors:
        return False, errors

    for field, allowed in _ENUM_FIELDS.items():
        if obj[field] not in allowed:
            errors.append("%s %r not in %s" % (field, obj[field], allowed))

    kf = obj["key_findings"]
    if not isinstance(kf, list):
        errors.append("key_findings must be a list")
    else:
        if len(kf) > MAX_KEY_FINDINGS:
            errors.append("more than %d key_findings" % MAX_KEY_FINDINGS)
        for i, k in enumerate(kf):
            if not isinstance(k, str) or not k.strip():
                errors.append("key_findings[%d] must be a non-empty string" % i)

    if not isinstance(obj["manipulation_detected"], bool):
        errors.append("manipulation_detected must be a boolean")

    return (not errors), errors
