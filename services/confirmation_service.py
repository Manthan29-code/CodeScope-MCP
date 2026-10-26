"""Human-approval gate for dangerous actions."""
from __future__ import annotations

import hmac
import secrets
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


class ApprovalError(Exception):
    pass


@dataclass
class PendingAction:
    action_id: str
    tool: str
    args: Dict[str, Any]
    summary: str
    fingerprint: str
    code: str
    expires_at: float
    attempts_left: int = 3


class ConfirmationService:
    MAX_PENDING = 20

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._pending: Dict[str, PendingAction] = {}
        self._lock = threading.Lock()

    @property
    def ttl(self) -> int:
        return self._ttl

    def _purge(self, now: float) -> None:
        for key in [k for k, v in self._pending.items() if v.expires_at <= now]:
            del self._pending[key]

    def create(self, tool: str, args: Dict[str, Any], summary: str, fingerprint: str) -> PendingAction:
        with self._lock:
            now = time.monotonic()
            self._purge(now)
            if len(self._pending) >= self.MAX_PENDING:
                raise ApprovalError("Too many pending approvals. Wait for them to expire.")
            action = PendingAction(
                action_id=secrets.token_urlsafe(8), tool=tool, args=args, summary=summary,
                fingerprint=fingerprint, code=f"{secrets.randbelow(1_000_000):06d}",
                expires_at=now + self._ttl,
            )
            self._pending[action.action_id] = action
        # OUT-OF-BAND: the code goes to the server console only.
        # Never return it to the LLM, never write it to a file inside the served project,
        # never send it through the logging system.
        print(
            f"\n[CodeScope] APPROVAL REQUIRED: {summary}\n"
            f"[CodeScope] Approval code: {action.code}  (expires in {self._ttl}s)\n",
            file=sys.stderr, flush=True,
        )
        return action

    def peek(self, action_id: str) -> PendingAction:
        with self._lock:
            self._purge(time.monotonic())
            action = self._pending.get(action_id)
            if not action:
                raise ApprovalError("Unknown or expired action_id")
            return action

    def consume(self, action_id: str, code: str, current_fingerprint: str) -> PendingAction:
        with self._lock:
            self._purge(time.monotonic())
            action = self._pending.get(action_id)
            if not action:
                raise ApprovalError("Unknown or expired action_id")
            if not hmac.compare_digest(str(code).strip().encode(), action.code.encode()):
                action.attempts_left -= 1
                if action.attempts_left <= 0:
                    del self._pending[action_id]
                    raise ApprovalError("Invalid approval code. Action cancelled; request it again.")
                raise ApprovalError("Invalid approval code")
            if current_fingerprint != action.fingerprint:
                del self._pending[action_id]
                raise ApprovalError("The repository changed since the preview. Request the action again.")
            del self._pending[action_id]
            return action


@dataclass
class GateOutcome:
    status: str                       # approved | pending | denied
    payload: Optional[Dict[str, Any]] = None


class ApprovalGate:
    def __init__(self, service: ConfirmationService, mode: str = "auto"):
        self.service = service
        self.mode = mode if mode in {"auto", "elicit", "code"} else "auto"

    async def gate(self, ctx, *, tool: str, args: Dict[str, Any], summary: str,
                   preview: str, fingerprint: str) -> GateOutcome:
        # Layer 2: ask the human directly through the client, if it supports elicitation.
        # (API shape follows FastMCP 2.x; verify against your installed version.)
        if self.mode in ("auto", "elicit") and ctx is not None:
            try:
                result = await ctx.elicit(
                    message=f"{summary}\n\n{preview[:3500]}\n\nApprove this action?",
                    response_type=None,
                )
            except Exception:
                if self.mode == "elicit":
                    return GateOutcome("denied", {
                        "ok": False,
                        "error": "GIT_CONFIRM_MODE=elicit but this client does not support elicitation.",
                    })
                # auto mode: fall through to the approval-code flow
            else:
                if getattr(result, "action", "") == "accept":
                    return GateOutcome("approved")
                return GateOutcome("denied", {"ok": False, "error": "The user declined this action."})

        # Layer 3: approval code shown only on the server console.
        action = self.service.create(tool, args, summary, fingerprint)
        return GateOutcome("pending", {
            "ok": True,
            "status": "approval_required",
            "action_id": action.action_id,
            "tool": tool,
            "summary": summary,
            "preview": preview,
            "expires_in_seconds": self.service.ttl,
            "instructions": (
                "STOP. Show this preview to the user and ask for approval. "
                "An approval code was displayed on the CodeScope server console, not here. "
                "Only after the user gives you that code, call confirm_action(action_id, approval_code). "
                "Never guess, invent or reuse a code."
            ),
        })
