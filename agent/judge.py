"""The judge: classifies a launch on top of the deterministic factsheet.

Pipeline for one launch:

    factsheet (facts + ceiling)
      -> model answer (structured judgment: verdict enum + finding keys
         + assessment enums, NO free text)
      -> schema validation            [reject + retry]
      -> key_findings ⊆ factsheet      [reject + retry]
      -> clamp verdict to ceiling (I3) [lower-only]
      -> manipulation floor            [manip ⇒ verdict ≤ FLAG]
      -> final verdict + assessments

The model is the only non-deterministic element and is boxed on every
side. It cannot exceed the ceiling (clamp), cannot invent finding text
(key_findings must be ours), cannot author feed copy (no free text), and
cannot silence the manipulation flag alone (a deterministic injection
scanner is ORed in). If the model refuses, judging stops (terminal); if
it merely fails a gate or the transport hiccups, the attempt is retried;
if no attempt passes, no verdict is produced (I4 — stay silent).
"""

from typing import Callable, Optional

from gavel.checks import FLAG, clamp_verdict, worse

from .policy import injection_signal
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import validate_verdict

MAX_ATTEMPTS = 3


class JudgeError(Exception):
    """No publishable verdict was produced (I4: stay silent, don't guess).
    Also raised for a deliberate model refusal (terminal, not retried)."""


ModelFn = Callable[[str, str], dict]
"""(system_prompt, user_prompt) -> parsed JSON object. Raises JudgeError
for a terminal refusal, or any other exception for a retryable failure.
Injectable so tests drive adversarial models with no network, and so the
provider is pure configuration (see agent/providers.py)."""


def _finding_names(factsheet: dict) -> set:
    return {name for name, _, _ in factsheet["findings"]}


def judge_factsheet(factsheet: dict, model: Optional[ModelFn] = None) -> dict:
    """Produce a gated, clamped structured verdict for one factsheet.

    Raises JudgeError if no attempt yields a gate-passing answer, or if
    the model refuses.
    """
    if model is None:
        from .providers import get_model
        model = get_model()

    ceiling = factsheet["ceiling"]
    user_prompt = build_user_prompt(factsheet)
    valid_names = _finding_names(factsheet)
    det_injection = injection_signal(factsheet)

    last_error = "no attempts made"
    for _ in range(MAX_ATTEMPTS):
        try:
            answer = model(SYSTEM_PROMPT, user_prompt)
        except JudgeError:
            raise  # deliberate refusal — terminal, do not retry
        except Exception as e:  # transport / parse — retryable
            last_error = "model call failed: %s" % e
            continue

        ok, errors = validate_verdict(answer)
        if not ok:
            last_error = "schema: %s" % "; ".join(errors)
            continue

        unknown = [k for k in answer["key_findings"] if k not in valid_names]
        if unknown:
            last_error = "key_findings not in factsheet: %s" % unknown
            continue

        clamped = clamp_verdict(answer["verdict"], ceiling)
        manipulation = bool(answer["manipulation_detected"]) or bool(det_injection)
        # A launch flagged as manipulative can never be published PASS.
        final = worse(clamped, FLAG) if manipulation else clamped

        return {
            "verdict": final,
            "model_verdict": answer["verdict"],
            "ceiling": ceiling,
            "clamped": final != answer["verdict"],
            "key_findings": answer["key_findings"],
            "hook_assessment": answer["hook_assessment"],
            "currency_assessment": answer["currency_assessment"],
            "recipient_assessment": answer["recipient_assessment"],
            "manipulation_detected": manipulation,
            "manipulation_model": bool(answer["manipulation_detected"]),
            "manipulation_deterministic": det_injection,
            "tx": factsheet["launch"]["tx"],
            "initializer": factsheet["launch"]["initializer"],
        }

    raise JudgeError("no publishable verdict after %d attempts: %s"
                     % (MAX_ATTEMPTS, last_error))
