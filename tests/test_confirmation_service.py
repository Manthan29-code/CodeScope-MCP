import pytest
import time
from services.confirmation_service import ApprovalError, ConfirmationService, ApprovalGate


def test_code_is_not_returned_and_wrong_code_fails(capsys):
    svc = ConfirmationService(ttl_seconds=60)
    action = svc.create("git_merge", {"branch": "x"}, "merge x", "fp1")
    assert action.code in capsys.readouterr().err  # printed on the console only

    # Wrong code decrements attempts
    wrong_code = "000000" if action.code != "000000" else "111111"
    with pytest.raises(ApprovalError, match="Invalid approval code"):
        svc.consume(action.action_id, wrong_code, "fp1")

    # Correct code and unchanged state succeeds
    consumed = svc.consume(action.action_id, action.code, "fp1")
    assert consumed.action_id == action.action_id

    # Second consume fails (already consumed)
    with pytest.raises(ApprovalError, match="Unknown or expired"):
        svc.consume(action.action_id, action.code, "fp1")


def test_wrong_code_cancels_after_3_attempts(capsys):
    svc = ConfirmationService(ttl_seconds=60)
    action = svc.create("git_merge", {"branch": "x"}, "merge x", "fp1")
    wrong_code = "000000" if action.code != "000000" else "111111"

    # Attempt 1
    with pytest.raises(ApprovalError, match="Invalid approval code"):
        svc.consume(action.action_id, wrong_code, "fp1")
    # Attempt 2
    with pytest.raises(ApprovalError, match="Invalid approval code"):
        svc.consume(action.action_id, wrong_code, "fp1")
    # Attempt 3 - cancelled
    with pytest.raises(ApprovalError, match="Action cancelled"):
        svc.consume(action.action_id, wrong_code, "fp1")

    # Further attempt fails with unknown/expired
    with pytest.raises(ApprovalError, match="Unknown or expired"):
        svc.consume(action.action_id, action.code, "fp1")


def test_expired_action():
    svc = ConfirmationService(ttl_seconds=1)
    action = svc.create("git_merge", {"branch": "x"}, "merge x", "fp1")
    time.sleep(1.1)

    with pytest.raises(ApprovalError, match="Unknown or expired"):
        svc.consume(action.action_id, action.code, "fp1")


def test_fingerprint_mismatch_cancels():
    svc = ConfirmationService(ttl_seconds=60)
    action = svc.create("git_merge", {"branch": "x"}, "merge x", "fp1")

    with pytest.raises(ApprovalError, match="repository changed"):
        svc.consume(action.action_id, action.code, "fp_different")

    # Action is also deleted upon mismatch
    with pytest.raises(ApprovalError, match="Unknown or expired"):
        svc.consume(action.action_id, action.code, "fp1")


def test_gate_code_fallback():
    import asyncio
    svc = ConfirmationService(ttl_seconds=60)
    gate = ApprovalGate(svc, mode="code")
    outcome = asyncio.run(
        gate.gate(
            None,
            tool="git_merge",
            args={"branch": "x"},
            summary="merge x",
            preview="preview diff",
            fingerprint="fp1",
        )
    )
    assert outcome.status == "pending"
    assert outcome.payload is not None
    assert outcome.payload["ok"] is True
    assert outcome.payload["status"] == "approval_required"
    assert "action_id" in outcome.payload
    # Ensure approval code is NOT in payload
    assert "code" not in outcome.payload
    assert svc.peek(outcome.payload["action_id"]).code not in str(outcome.payload)
