"""016 T016/T017 — the baseline workflow's transition table (allowed/forbidden, guards on who acts, required
comment, reopen window); custom workflows are validated (closed schema, unknown/unreachable states and dead
ends refused); ticket type fields: types, required fields named, staff-only fields hidden from requesters."""

import pytest

from portalab.core.errors import ValidationFailed
from portalab.modules.support.workflow.engine import (
    BASELINE,
    TransitionForbidden,
    WorkflowInvalid,
    available,
    check,
    parse,
)
from portalab.modules.support.workflow.types import (
    BASELINE_TYPES,
    FieldsInvalid,
    RequiredFieldsMissing,
    parse_fields,
    validate_values,
    visible_fields,
)

WORKFLOW = parse(BASELINE)


def test_baseline_transitions() -> None:
    assert {t.key for t in available(WORKFLOW, "open", {"requester"}, reopen_open=True)} == {"cancel"}
    assert {t.key for t in available(WORKFLOW, "open", {"staff"}, reopen_open=True)} == {
        "start",
        "resolve",
        "cancel",
    }
    assert (
        check(WORKFLOW, "open", "start", {"staff"}, has_comment=False, reopen_open=True).target.key
        == "in_progress"
    )
    with pytest.raises(TransitionForbidden):
        check(WORKFLOW, "open", "start", {"requester"}, has_comment=False, reopen_open=True)  # wrong actor
    with pytest.raises(TransitionForbidden):
        check(WORKFLOW, "closed", "reopen", {"staff"}, has_comment=False, reopen_open=True)  # wrong state
    with pytest.raises(ValidationFailed) as comment:
        check(WORKFLOW, "in_progress", "ask_user", {"staff"}, has_comment=False, reopen_open=True)
    assert comment.value.code == "ticket.comment_required"
    assert (
        check(WORKFLOW, "resolved", "reopen", {"requester"}, has_comment=False, reopen_open=True).target.key
        == "open"
    )
    with pytest.raises(TransitionForbidden) as late:
        check(WORKFLOW, "resolved", "reopen", {"requester"}, has_comment=False, reopen_open=False)
    assert late.value.code == "ticket.reopen_window_passed"
    assert check(WORKFLOW, "resolved", "reopen", {"staff"}, has_comment=False, reopen_open=False)  # staff may
    assert check(WORKFLOW, "open", "resolve", {"assignee"}, has_comment=False, reopen_open=True)


def test_custom_workflow_validation() -> None:
    good = {
        "states": [
            {"key": "new", "label": "New", "kind": "open"},
            {"key": "done", "label": "Done", "kind": "closed", "terminal": True},
        ],
        "initial": "new",
        "transitions": [
            {"key": "finish", "label": "Finish", "from": ["new"], "to": "done", "who": ["staff"]}
        ],
    }
    assert parse(good).initial == "new"
    for broken, message in (
        ({**good, "initial": "ghost"}, "unknown initial"),
        (
            {**good, "states": [*good["states"], {"key": "limbo", "label": "L", "kind": "waiting"}]},
            "unreachable",
        ),
        (
            {
                **good,
                "states": [*good["states"], {"key": "stuck", "label": "S", "kind": "waiting"}],
                "transitions": [
                    *good["transitions"],
                    {"key": "park", "label": "P", "from": ["new"], "to": "stuck", "who": ["staff"]},
                ],
            },
            "dead end",
        ),
        ({**good, "script": "rm -rf /"}, "schema"),
        (
            {
                **good,
                "transitions": [
                    {"key": "x", "label": "X", "from": ["new"], "to": "nowhere", "who": ["staff"]}
                ],
            },
            "unknown state",
        ),
    ):
        with pytest.raises(WorkflowInvalid) as error:
            parse(broken)
        assert message in str(error.value.extensions) or message == "schema", (
            message,
            error.value.extensions,
        )


def test_type_fields() -> None:
    access = parse_fields(next(t for t in BASELINE_TYPES if t["key"] == "access_request")["fields"])
    with pytest.raises(RequiredFieldsMissing) as missing:
        validate_values(access, {"resource": "Media"})
    assert missing.value.extensions["fields"] == ["justification"]
    values = validate_values(access, {"resource": "Media", "justification": "family", "staff_notes": "ok"})
    assert visible_fields(access, values, staff=False) == {"resource": "Media", "justification": "family"}
    assert "staff_notes" in visible_fields(access, values, staff=True)
    bug = parse_fields(next(t for t in BASELINE_TYPES if t["key"] == "bug")["fields"])
    for bad in ({"steps": "x", "impact": "catastrophic"}, {"steps": "x", "nope": 1}, {"steps": 42}):
        with pytest.raises(FieldsInvalid):
            validate_values(bug, bad)
    with pytest.raises(FieldsInvalid):
        parse_fields([{"key": "s", "label": "S", "type": "select"}])  # select without options
