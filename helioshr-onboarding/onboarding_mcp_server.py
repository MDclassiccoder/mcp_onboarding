#!/usr/bin/env python3
"""
HeliosHR Onboarding MCP Server
================================
Exposes the onboarding orchestration workflow as MCP tools over stdio transport.
Each tool maps to a discrete step in the provisioning lifecycle so that an
AI agent (or human operator) can drive onboarding interactively.

Start the server:
    python onboarding_mcp_server.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# Re-use core logic from the orchestrator
from onboarding_orchestrator import (
    AUDIT_LOG,
    audit,
    load_role_policy,
    load_sample_payloads,
    mock_claude_role_mapping,
    mock_provision_freshservice,
    mock_provision_google,
    mock_provision_jira,
    mock_provision_okta,
    mock_provision_slack,
    mock_rollback_google,
    mock_rollback_okta,
    write_audit_log,
    CONFIDENCE_THRESHOLD,
    BASE_DIR,
)

# ---------------------------------------------------------------------------
# In-memory state store (keyed by employee_id)
# ---------------------------------------------------------------------------
provisioning_state: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "HeliosHR Onboarding",
    version="1.0.0",
)


@mcp.tool()
def provision_user(hire_record: dict) -> dict:
    """Run the full provisioning workflow for a new hire.

    Accepts a Workday webhook payload (or the inner 'employee' object) and
    sequentially provisions Okta, Google Workspace, Slack, Jira, and
    FreshService. Returns the complete provisioning result including any
    rollback actions if a step fails.

    Args:
        hire_record: A Workday webhook payload dict containing an 'employee'
            key with fields: employee_id, first_name, last_name, email,
            department, job_title, manager, manager_email, start_date,
            location, employment_type, and optionally contract_end_date.
    """
    # Normalize: accept either the full payload or just the employee object
    if "employee" not in hire_record and "employee_id" in hire_record:
        hire_record = {"employee": hire_record}

    emp = hire_record["employee"]
    emp_id = emp["employee_id"]
    policy = load_role_policy()

    # AI role mapping
    mapping = mock_claude_role_mapping(hire_record, policy)

    # Check confidence
    if mapping["confidence"] < CONFIDENCE_THRESHOLD:
        state = {
            "employee_id": emp_id,
            "status": "escalated",
            "reason": (
                f"AI confidence {mapping['confidence']:.0%} below threshold "
                f"for department '{emp['department']}'"
            ),
            "mapping": mapping,
            "completed_steps": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        provisioning_state[emp_id] = state
        audit("provision_user", "escalated", state)
        return state

    # Sequential provisioning
    profile = mapping["access_profile"]
    completed: list[str] = []
    results: dict[str, Any] = {}

    steps = [
        ("Okta", lambda: mock_provision_okta(emp, profile["okta_groups"])),
        ("Google Workspace", lambda: mock_provision_google(emp, profile["google_workspace_ou"])),
        ("Slack", lambda: mock_provision_slack(emp, profile["slack_channels"])),
        ("Jira", lambda: mock_provision_jira(emp, profile["jira_projects"])),
        (
            "FreshService",
            lambda: mock_provision_freshservice(
                emp, profile["freshservice_category"], mapping["ticket_description"]
            ),
        ),
    ]

    for step_name, step_fn in steps:
        result = step_fn()
        results[step_name] = result
        if result["success"]:
            completed.append(step_name)
            audit(f"provision_{step_name.lower().replace(' ', '_')}", "success", result["response"])
        else:
            audit(f"provision_{step_name.lower().replace(' ', '_')}", "failure", result["response"])
            # Rollback
            rollback_fns: dict[str, Any] = {
                "Okta": lambda: mock_rollback_okta(emp),
                "Google Workspace": lambda: mock_rollback_google(emp),
            }
            rolled_back = []
            for prev in reversed(completed):
                if prev in rollback_fns:
                    rb = rollback_fns[prev]()
                    rolled_back.append(prev)
                    audit(f"rollback_{prev.lower().replace(' ', '_')}", "success" if rb["success"] else "failure", rb.get("response", {}))

            state = {
                "employee_id": emp_id,
                "status": "failed",
                "failed_at": step_name,
                "rolled_back": rolled_back,
                "completed_steps": completed,
                "results": results,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            provisioning_state[emp_id] = state
            return state

    state = {
        "employee_id": emp_id,
        "status": "completed",
        "completed_steps": completed,
        "results": results,
        "welcome_message": mapping["welcome_message"],
        "confidence": mapping["confidence"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    provisioning_state[emp_id] = state
    audit("provision_user", "completed", {"employee_id": emp_id})
    write_audit_log(BASE_DIR / "audit_log.json")
    return state


@mcp.tool()
def check_provisioning_status(employee_id: str) -> dict:
    """Check the current provisioning status for an employee.

    Returns the full provisioning state including which steps completed,
    any failures, and the current status (pending, completed, failed,
    escalated, or rolled_back).

    Args:
        employee_id: The employee ID to look up (e.g. 'EMP-20260328-001').
    """
    if employee_id in provisioning_state:
        return provisioning_state[employee_id]
    return {
        "employee_id": employee_id,
        "status": "not_found",
        "message": "No provisioning record found for this employee ID.",
    }


@mcp.tool()
def rollback_user(employee_id: str) -> dict:
    """Roll back all provisioned accounts for an employee.

    Deactivates the Okta account and suspends the Google Workspace account.
    Slack, Jira, and FreshService do not have automated rollback — those
    are flagged for manual cleanup.

    Args:
        employee_id: The employee ID to roll back (e.g. 'EMP-20260328-001').
    """
    if employee_id not in provisioning_state:
        return {
            "employee_id": employee_id,
            "status": "not_found",
            "message": "No provisioning record found. Nothing to roll back.",
        }

    state = provisioning_state[employee_id]
    if state["status"] == "rolled_back":
        return {
            "employee_id": employee_id,
            "status": "already_rolled_back",
            "message": "This employee was already rolled back.",
        }

    # Build a minimal emp dict for rollback functions
    emp = {"email": f"{employee_id}@helioshr.com"}
    # Try to reconstruct from state
    if "results" in state and "Okta" in state["results"]:
        okta_resp = state["results"]["Okta"].get("response", {})
        profile = okta_resp.get("profile", {})
        emp.update({
            "email": profile.get("email", emp["email"]),
            "first_name": profile.get("firstName", ""),
            "last_name": profile.get("lastName", ""),
        })

    rollback_results: dict[str, Any] = {}
    completed = state.get("completed_steps", [])

    auto_rollback = {"Okta", "Google Workspace"}
    manual_cleanup = {"Slack", "Jira", "FreshService"}

    for step in completed:
        if step == "Okta":
            rollback_results["Okta"] = mock_rollback_okta(emp)
        elif step == "Google Workspace":
            rollback_results["Google Workspace"] = mock_rollback_google(emp)
        elif step in manual_cleanup:
            rollback_results[step] = {
                "success": True,
                "action": "flagged_for_manual_cleanup",
                "message": f"{step} account flagged for manual removal.",
            }

    state["status"] = "rolled_back"
    state["rollback_results"] = rollback_results
    state["rollback_timestamp"] = datetime.now(timezone.utc).isoformat()
    provisioning_state[employee_id] = state

    audit("rollback_user", "success", {
        "employee_id": employee_id,
        "rollback_results": rollback_results,
    })
    write_audit_log(BASE_DIR / "audit_log.json")

    return {
        "employee_id": employee_id,
        "status": "rolled_back",
        "rollback_results": rollback_results,
    }


@mcp.tool()
def get_role_policy(department: str) -> dict:
    """Return the access mapping policy for a given department.

    Looks up the department in role_policy.json and returns the full
    access profile including Okta groups, Google Workspace OU, Slack
    channels, Jira projects, FreshService category, and whether
    manager approval is required.

    Args:
        department: Department name (e.g. 'Engineering', 'InfoSec').
    """
    policy = load_role_policy()
    if department in policy:
        return {
            "department": department,
            "found": True,
            "policy": policy[department],
        }
    # Suggest close matches
    available = list(policy.keys())
    return {
        "department": department,
        "found": False,
        "message": f"Department '{department}' not found in policy.",
        "available_departments": available,
    }


@mcp.tool()
def escalate_to_it(employee_id: str, reason: str) -> dict:
    """Log an escalation request to the IT onboarding review channel.

    Creates a structured escalation record that would be posted to
    #it-onboarding-review in Slack. Use this when AI confidence is low,
    when a department is ambiguous, or when manual intervention is needed.

    Args:
        employee_id: The employee ID to escalate (e.g. 'EMP-20260328-001').
        reason: Human-readable reason for the escalation.
    """
    escalation = {
        "employee_id": employee_id,
        "reason": reason,
        "channel": "#it-onboarding-review",
        "status": "escalated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": (
            f":warning: *Onboarding Escalation*\n"
            f"Employee ID: {employee_id}\n"
            f"Reason: {reason}\n"
            f"Action Required: Please review and manually assign the "
            f"correct access profile in the HeliosHR admin console."
        ),
    }

    # Update state if exists
    if employee_id in provisioning_state:
        provisioning_state[employee_id]["status"] = "escalated"
        provisioning_state[employee_id]["escalation"] = escalation

    audit("escalate_to_it", "success", escalation)
    write_audit_log(BASE_DIR / "audit_log.json")

    return escalation


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(transport="stdio")
