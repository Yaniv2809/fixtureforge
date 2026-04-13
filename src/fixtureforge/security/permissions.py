"""
FixtureForge Security Layer — Permission Gates + Mailbox Pattern.

Architecture (inspired by multi-agent coordination):
  DataAgent generates data but CANNOT self-approve sensitive/dangerous ops.
  Instead it posts to a mailbox → ForgeCoordinator evaluates → approve/reject.
  Atomic Claim (threading.Lock) prevents two agents from racing on the same request.

Three sensitivity levels:
  SAFE      — user records, product data              → auto-approved always
  SENSITIVE — PII, financial data                     → requires FORGE_ALLOW_PII=1
  DANGEROUS — SQL injection, fuzz payloads, exploits  → requires interactive human prompt
"""
from __future__ import annotations

import os
import threading
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Type

if TYPE_CHECKING:
    from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Sensitivity enum
# ---------------------------------------------------------------------------

class DataSensitivity(Enum):
    SAFE      = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


# ---------------------------------------------------------------------------
# Field-pattern tables
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS: frozenset[str] = frozenset({
    # Identity / government
    "ssn", "social_security", "passport", "tax_id", "national_id", "nin",
    "license", "driving_license",
    # Financial
    "credit_card", "card_number", "cvv", "pin", "bank_account",
    "routing_number", "iban", "swift", "salary", "income",
    # Auth / secrets
    "password", "secret", "token", "api_key", "private_key",
    "access_token", "refresh_token", "session",
    # Biometric / medical
    "fingerprint", "retina", "biometric", "medical", "diagnosis",
    "prescription", "health",
    # PII
    "date_of_birth", "dob", "birth_date", "birth",
    "ip_address", "device_id", "mac_address",
    "geolocation", "latitude", "longitude",
})

_DANGEROUS_PATTERNS: frozenset[str] = frozenset({
    "sql_injection", "xss", "xss_payload", "fuzz", "fuzz_input",
    "malformed", "overflow", "buffer_overflow", "injection",
    "exploit", "payload", "attack", "evil", "shell", "shellcode",
    "command_injection", "path_traversal",
})


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class FieldPermissionChecker:
    """
    Classifies individual fields or entire Pydantic models by data sensitivity.
    Checks field names using word-boundary splitting (avoids partial matches).
    """

    @staticmethod
    def classify_field(field_name: str) -> DataSensitivity:
        name_lower = field_name.lower()
        parts = set(name_lower.split("_"))

        for pattern in _DANGEROUS_PATTERNS:
            if pattern in parts or pattern in name_lower:
                return DataSensitivity.DANGEROUS

        for pattern in _SENSITIVE_PATTERNS:
            if pattern in parts or pattern in name_lower:
                return DataSensitivity.SENSITIVE

        return DataSensitivity.SAFE

    @staticmethod
    def classify_model(model: "Type[BaseModel]") -> DataSensitivity:
        """Return the *highest* sensitivity level found in any field of the model."""
        highest = DataSensitivity.SAFE
        for field_name in model.model_fields:
            level = FieldPermissionChecker.classify_field(field_name)
            if level == DataSensitivity.DANGEROUS:
                return DataSensitivity.DANGEROUS
            if level == DataSensitivity.SENSITIVE:
                highest = DataSensitivity.SENSITIVE
        return highest

    @staticmethod
    def sensitive_fields(model: "Type[BaseModel]") -> List[str]:
        """Return list of field names that are SENSITIVE or DANGEROUS."""
        return [
            name for name in model.model_fields
            if FieldPermissionChecker.classify_field(name) != DataSensitivity.SAFE
        ]


# ---------------------------------------------------------------------------
# Mailbox internals
# ---------------------------------------------------------------------------

class _ApprovalRequest:
    """An approval request sitting in the ForgeCoordinator mailbox."""

    __slots__ = ("agent_id", "model_name", "sensitivity", "count")

    def __init__(
        self,
        agent_id: str,
        model_name: str,
        sensitivity: DataSensitivity,
        count: int,
    ) -> None:
        self.agent_id   = agent_id
        self.model_name = model_name
        self.sensitivity = sensitivity
        self.count      = count


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class ForgeCoordinator:
    """
    Central coordinator implementing the Mailbox Pattern.

    DataAgents call ``request_approval()``.
    The coordinator evaluates the request and returns True (approved) or False (rejected).
    A threading.Lock provides the Atomic Claim — no two agents can race through
    a dangerous gate simultaneously.

    Parameters
    ----------
    allow_pii : bool, optional
        Auto-approve SENSITIVE requests.  Defaults to env var FORGE_ALLOW_PII.
    interactive : bool
        When True, prompt the user interactively for SENSITIVE/DANGEROUS requests
        that are not auto-approved.  Set False in CI/headless environments.
    """

    def __init__(
        self,
        allow_pii: Optional[bool] = None,
        interactive: bool = True,
    ) -> None:
        self._allow_pii = (
            allow_pii
            if allow_pii is not None
            else os.environ.get("FORGE_ALLOW_PII", "0").strip().lower()
            in ("1", "true", "yes")
        )
        self._interactive = interactive
        self._lock = threading.Lock()    # Atomic Claim — one gate at a time
        self._mailbox: List[_ApprovalRequest] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_approval(
        self,
        agent_id: str,
        model_name: str,
        sensitivity: DataSensitivity,
        count: int,
    ) -> bool:
        """
        Submit an approval request.  Returns True if generation is approved.

        SAFE      → immediately True (no lock needed)
        SENSITIVE → auto-approved if allow_pii, else prompt
        DANGEROUS → always requires interactive human confirmation
        """
        if sensitivity == DataSensitivity.SAFE:
            return True

        req = _ApprovalRequest(agent_id, model_name, sensitivity, count)

        # Atomic Claim — serialize approval decisions
        with self._lock:
            self._mailbox.append(req)
            approved = self._evaluate(req)
            self._mailbox.remove(req)

        return approved

    def check_and_approve(self, model: "Type[BaseModel]", count: int) -> bool:
        """
        Convenience: classify *model* then request approval in one call.
        Returns True when generation may proceed.
        """
        sensitivity = FieldPermissionChecker.classify_model(model)
        agent_id = f"DataAgent[{model.__name__}]"
        return self.request_approval(agent_id, model.__name__, sensitivity, count)

    # ------------------------------------------------------------------
    # Internal evaluation
    # ------------------------------------------------------------------

    def _evaluate(self, req: _ApprovalRequest) -> bool:
        if req.sensitivity == DataSensitivity.SENSITIVE:
            if self._allow_pii:
                return True
            flagged = self._format_gate_banner(req)
            print(flagged)
            if self._interactive:
                return self._prompt_user(req)
            return False

        if req.sensitivity == DataSensitivity.DANGEROUS:
            print(self._format_gate_banner(req))
            if self._interactive:
                return self._prompt_user(req)
            return False

        return False

    def _format_gate_banner(self, req: _ApprovalRequest) -> str:
        icon  = "⚠️ " if req.sensitivity == DataSensitivity.SENSITIVE else "🚨"
        label = "SENSITIVE DATA" if req.sensitivity == DataSensitivity.SENSITIVE else "DANGEROUS DATA"
        hint  = (
            "Set FORGE_ALLOW_PII=1 to auto-approve PII generation."
            if req.sensitivity == DataSensitivity.SENSITIVE
            else "This model contains fields designed for security testing (injections, fuzzing)."
        )
        return (
            f"\n{icon} {label} GATE\n"
            f"   Model  : {req.model_name}\n"
            f"   Records: {req.count}\n"
            f"   Agent  : {req.agent_id}\n"
            f"   {hint}\n"
        )

    def _prompt_user(self, req: _ApprovalRequest) -> bool:
        try:
            answer = input(
                f"   Approve generation of {req.count} × {req.model_name}? [y/N]: "
            )
            return answer.strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            print("\n   [Denied — non-interactive environment]")
            return False
