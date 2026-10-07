import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import models  # noqa: E402
import report_pipeline as rp  # noqa: E402


def test_can_act_matches_stage_owner():
    assert rp.can_act(models.REPORT_REPORTER, "pentester")
    assert rp.can_act(models.REPORT_REPORTER, "lead_pentester")   # lead may act everywhere it owns
    assert not rp.can_act(models.REPORT_REPORTER, "governance")
    assert not rp.can_act(models.REPORT_REPORTER, "lead_cyber")
    assert rp.can_act(models.REPORT_LEAD, "lead_pentester")
    assert not rp.can_act(models.REPORT_LEAD, "pentester")
    assert rp.can_act(models.REPORT_GOVERNANCE, "governance")


def test_advance_forward_path():
    assert rp.advance(models.REPORT_REPORTER, "pentester") == models.REPORT_LEAD
    assert rp.advance(models.REPORT_LEAD, "lead_pentester") == models.REPORT_GOVERNANCE
    assert rp.advance(models.REPORT_GOVERNANCE, "governance") == models.REPORT_DELIVERED


def test_advance_wrong_role_denied():
    try:
        rp.advance(models.REPORT_REPORTER, "governance")
        raise SystemExit("expected PermissionError")
    except PermissionError:
        pass


def test_advance_past_delivered_invalid():
    try:
        rp.advance(models.REPORT_DELIVERED, "governance")
        raise SystemExit("expected ValueError")
    except ValueError:
        pass


def test_send_back_one_stage():
    assert rp.send_back(models.REPORT_LEAD, "lead_pentester") == models.REPORT_REPORTER
    assert rp.send_back(models.REPORT_GOVERNANCE, "governance") == models.REPORT_LEAD


def test_send_back_from_first_stage_invalid():
    try:
        rp.send_back(models.REPORT_REPORTER, "pentester")
        raise SystemExit("expected ValueError")
    except ValueError:
        pass
