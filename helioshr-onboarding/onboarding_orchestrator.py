#!/usr/bin/env python3
"""
HeliosHR Onboarding Orchestrator
=================================
Automates employee provisioning across Okta, Google Workspace, Slack, Jira,
and FreshService using AI-driven role mapping. All external API calls and
Claude AI calls are mocked for demonstration purposes.

Usage:
    python onboarding_orchestrator.py                    # Normal Engineering hire
    python onboarding_orchestrator.py --simulate-failure # Force Slack failure + rollback
    python onboarding_orchestrator.py --edge-case        # Ambiguous department escalation
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# ANSI color helpers (no external deps)
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Force UTF-8 output on Windows so unicode icons render correctly
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


def _log(icon: str, color: str, message: str) -> None:
    """Print a colored status line to the terminal."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"  {DIM}{timestamp}{RESET}  {color}{icon}{RESET}  {message}")


def log_ok(msg: str) -> None:
    _log("\u2713", GREEN, msg)


def log_fail(msg: str) -> None:
    _log("\u2717", RED, msg)


def log_warn(msg: str) -> None:
    _log("!", YELLOW, msg)


def log_info(msg: str) -> None:
    _log("\u2022", CYAN, msg)


def section(title: str) -> None:
    print(f"\n  {BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"  {BOLD}{CYAN}{title}{RESET}")
    print(f"  {BOLD}{CYAN}{'=' * 60}{RESET}\n")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
AUDIT_LOG: list[dict[str, Any]] = []


def audit(action: str, status: str, details: dict[str, Any] | None = None) -> None:
    """Append a structured entry to the in-memory audit log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "status": status,
        "details": details or {},
    }
    AUDIT_LOG.append(entry)


def write_audit_log(path: Path) -> None:
    """Flush the audit log to disk as pretty-printed JSON."""
    path.write_text(json.dumps(AUDIT_LOG, indent=2))
    log_info(f"Audit log written to {path}")


# ---------------------------------------------------------------------------
# Load policy & payloads
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent


def load_role_policy() -> dict[str, Any]:
    return json.loads((BASE_DIR / "role_policy.json").read_text())


def load_sample_payloads() -> list[dict[str, Any]]:
    data = json.loads((BASE_DIR / "sample_payloads.json").read_text())
    return data["payloads"]


# ---------------------------------------------------------------------------
# Mock Claude AI agent
# ---------------------------------------------------------------------------
def mock_claude_role_mapping(
    hire: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    """
    Simulates a Claude API call that reads the hire record + role_policy.json
    and returns an access profile, welcome message, ticket description, and
    confidence score.

    If the hire's department exists in the policy, confidence is high.
    Otherwise, Claude returns a best-guess with low confidence.
    """
    emp = hire["employee"]
    department = emp["department"]
    name = f"{emp['first_name']} {emp['last_name']}"
    title = emp["job_title"]
    start = emp["start_date"]

    # Check for exact department match
    if department in policy:
        profile = policy[department]
        confidence = 0.95
    else:
        # Claude's best-guess: fall back to Engineering for anything with
        # "Engineering" in the name, otherwise pick People Operations.
        if "engineering" in department.lower():
            profile = policy["Engineering"]
            guess_dept = "Engineering"
        else:
            profile = policy["People Operations"]
            guess_dept = "People Operations"
        confidence = 0.62  # below threshold
        log_warn(
            f"Claude AI: department '{department}' not in policy. "
            f"Best guess -> '{guess_dept}' (confidence {confidence})"
        )

    # Adjust for contractor: flag time-bounded access
    access_note = ""
    if emp.get("employment_type") == "contractor":
        end_date = emp.get("contract_end_date", "TBD")
        access_note = f" (contractor — access expires {end_date})"

    welcome_message = (
        f":wave: Welcome to HeliosHR, *{name}*! :tada:\n"
        f"You're joining us as *{title}*{access_note}. "
        f"Your start date is *{start}*.\n"
        f"Your manager *{emp['manager']}* has been notified and will reach "
        f"out with onboarding details. In the meantime, check out "
        f"#new-hires for helpful resources!\n"
        f"We're excited to have you on board. :rocket:"
    )

    ticket_description = (
        f"New hire onboarding request for {name} ({emp['employee_id']}).\n"
        f"Department: {department}\n"
        f"Title: {title}\n"
        f"Start Date: {start}\n"
        f"Manager: {emp['manager']} ({emp['manager_email']})\n"
        f"Location: {emp['location']}\n"
        f"Employment Type: {emp['employment_type']}\n\n"
        f"Provisioning includes: Okta groups, Google Workspace OU, "
        f"Slack channels, Jira projects, and FreshService category "
        f"as defined by the {department} access policy."
    )

    return {
        "access_profile": {
            "okta_groups": profile["okta_groups"],
            "google_workspace_ou": profile["google_workspace_ou"],
            "slack_channels": profile["slack_channels"],
            "jira_projects": profile["jira_projects"],
            "freshservice_category": profile["freshservice_category"],
            "requires_approval": profile["requires_approval"],
        },
        "welcome_message": welcome_message,
        "ticket_description": ticket_description,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Mock SaaS API provisioning functions
# ---------------------------------------------------------------------------
def mock_provision_okta(
    emp: dict[str, Any], groups: list[str]
) -> dict[str, Any]:
    """Mock Okta user creation + group assignment."""
    okta_user_id = f"okta-{uuid.uuid4().hex[:12]}"
    return {
        "success": True,
        "provider": "Okta",
        "response": {
            "id": okta_user_id,
            "status": "PROVISIONED",
            "profile": {
                "login": emp["email"],
                "firstName": emp["first_name"],
                "lastName": emp["last_name"],
                "email": emp["email"],
            },
            "groups_assigned": groups,
            "_links": {
                "self": f"https://helioshr.okta.com/api/v1/users/{okta_user_id}"
            },
        },
    }


def mock_provision_google(
    emp: dict[str, Any], ou: str
) -> dict[str, Any]:
    """Mock Google Workspace account creation."""
    return {
        "success": True,
        "provider": "Google Workspace",
        "response": {
            "kind": "admin#directory#user",
            "id": f"gws-{uuid.uuid4().hex[:12]}",
            "primaryEmail": emp["email"],
            "orgUnitPath": ou,
            "isMailboxSetup": True,
            "creationTime": datetime.now(timezone.utc).isoformat(),
        },
    }


def mock_provision_slack(
    emp: dict[str, Any], channels: list[str], *, force_fail: bool = False
) -> dict[str, Any]:
    """Mock Slack invite + channel joins. Optionally force a failure."""
    if force_fail:
        return {
            "success": False,
            "provider": "Slack",
            "response": {
                "ok": False,
                "error": "user_not_found",
                "detail": (
                    "The Slack SCIM connector could not locate a matching "
                    "user profile. This usually indicates an email mismatch "
                    "between the IdP and Slack workspace."
                ),
            },
        }
    slack_user_id = f"U{uuid.uuid4().hex[:10].upper()}"
    return {
        "success": True,
        "provider": "Slack",
        "response": {
            "ok": True,
            "user": {
                "id": slack_user_id,
                "name": emp["email"].split("@")[0],
                "real_name": f"{emp['first_name']} {emp['last_name']}",
            },
            "channels_joined": channels,
            "invite_sent": True,
        },
    }


def mock_provision_jira(
    emp: dict[str, Any], projects: list[str]
) -> dict[str, Any]:
    """Mock Jira Cloud user + project role assignment."""
    return {
        "success": True,
        "provider": "Jira",
        "response": {
            "accountId": f"jira-{uuid.uuid4().hex[:12]}",
            "emailAddress": emp["email"],
            "displayName": f"{emp['first_name']} {emp['last_name']}",
            "active": True,
            "projects_assigned": projects,
        },
    }


def mock_provision_freshservice(
    emp: dict[str, Any], category: str, ticket_desc: str
) -> dict[str, Any]:
    """Mock FreshService onboarding ticket creation."""
    ticket_id = f"FS-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "provider": "FreshService",
        "response": {
            "ticket": {
                "id": ticket_id,
                "subject": (
                    f"Onboarding: {emp['first_name']} {emp['last_name']} "
                    f"— {emp['job_title']}"
                ),
                "category": category,
                "status": "Open",
                "priority": "Medium",
                "description": ticket_desc,
                "requester_email": emp["manager_email"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


# ---------------------------------------------------------------------------
# Mock rollback functions
# ---------------------------------------------------------------------------
def mock_rollback_okta(emp: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "provider": "Okta",
        "action": "deactivate_and_delete",
        "response": {"status": "DEPROVISIONED", "login": emp["email"]},
    }


def mock_rollback_google(emp: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "provider": "Google Workspace",
        "action": "suspend_account",
        "response": {"primaryEmail": emp["email"], "suspended": True},
    }


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------
CONFIDENCE_THRESHOLD = 0.8


def escalate(emp: dict[str, Any], mapping: dict[str, Any]) -> None:
    """Log what would be posted to #it-onboarding-review."""
    section("ESCALATION: Low-Confidence Role Mapping")
    name = f"{emp['first_name']} {emp['last_name']}"
    log_warn(f"Confidence {mapping['confidence']:.2f} < threshold {CONFIDENCE_THRESHOLD}")
    log_warn(f"Department '{emp['department']}' requires manual review")

    escalation_msg = (
        f":warning: *Onboarding Escalation — Manual Review Required*\n"
        f"Employee: {name} ({emp['employee_id']})\n"
        f"Department: {emp['department']}\n"
        f"Title: {emp['job_title']}\n"
        f"AI Confidence: {mapping['confidence']:.0%}\n\n"
        f"The AI could not confidently map this hire to an existing "
        f"department policy. Please review and assign the correct access "
        f"profile in the HeliosHR admin console."
    )

    log_info("Would post to #it-onboarding-review:")
    for line in escalation_msg.split("\n"):
        print(f"      {DIM}{line}{RESET}")

    audit("escalation", "triggered", {
        "employee_id": emp["employee_id"],
        "department": emp["department"],
        "confidence": mapping["confidence"],
        "channel": "#it-onboarding-review",
        "message": escalation_msg,
    })


# ---------------------------------------------------------------------------
# Provisioning pipeline with compensating rollback
# ---------------------------------------------------------------------------
def run_provisioning(
    hire: dict[str, Any],
    mapping: dict[str, Any],
    *,
    simulate_failure: bool = False,
) -> dict[str, Any]:
    """
    Execute the sequential provisioning pipeline:
        Okta -> Google Workspace -> Slack -> Jira -> FreshService

    If any step fails, previously completed steps are rolled back in
    reverse order (compensating transaction pattern).
    """
    emp = hire["employee"]
    profile = mapping["access_profile"]
    completed: list[str] = []  # track successful steps for rollback

    steps: list[tuple[str, Any]] = [
        (
            "Okta",
            lambda: mock_provision_okta(emp, profile["okta_groups"]),
        ),
        (
            "Google Workspace",
            lambda: mock_provision_google(emp, profile["google_workspace_ou"]),
        ),
        (
            "Slack",
            lambda: mock_provision_slack(
                emp, profile["slack_channels"], force_fail=simulate_failure
            ),
        ),
        (
            "Jira",
            lambda: mock_provision_jira(emp, profile["jira_projects"]),
        ),
        (
            "FreshService",
            lambda: mock_provision_freshservice(
                emp, profile["freshservice_category"], mapping["ticket_description"]
            ),
        ),
    ]

    results: dict[str, Any] = {}

    section("Provisioning Pipeline")

    for step_name, step_fn in steps:
        log_info(f"Provisioning {step_name}...")
        result = step_fn()
        results[step_name] = result

        if result["success"]:
            log_ok(f"{step_name} provisioned successfully")
            audit(f"provision_{step_name.lower().replace(' ', '_')}", "success", result["response"])
            completed.append(step_name)
        else:
            log_fail(f"{step_name} provisioning FAILED: {result['response'].get('error', 'unknown')}")
            audit(
                f"provision_{step_name.lower().replace(' ', '_')}",
                "failure",
                result["response"],
            )

            # --- Compensating rollback ---
            if completed:
                section("Compensating Rollback")
                log_warn(
                    f"Rolling back {len(completed)} completed step(s) due to "
                    f"{step_name} failure"
                )

                rollback_fns: dict[str, Any] = {
                    "Okta": lambda: mock_rollback_okta(emp),
                    "Google Workspace": lambda: mock_rollback_google(emp),
                }

                for prev_step in reversed(completed):
                    if prev_step in rollback_fns:
                        rb_result = rollback_fns[prev_step]()
                        if rb_result["success"]:
                            log_ok(f"Rolled back {prev_step}")
                            audit(
                                f"rollback_{prev_step.lower().replace(' ', '_')}",
                                "success",
                                rb_result["response"],
                            )
                        else:
                            log_fail(f"Rollback of {prev_step} FAILED — manual intervention needed")
                            audit(
                                f"rollback_{prev_step.lower().replace(' ', '_')}",
                                "failure",
                                rb_result.get("response", {}),
                            )
                    else:
                        log_warn(f"No rollback handler for {prev_step} — skipped")

            results["_pipeline_status"] = "failed"
            results["_failed_at"] = step_name
            results["_rolled_back"] = list(reversed(completed))
            return results

    results["_pipeline_status"] = "completed"
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="HeliosHR AI-Powered Onboarding Orchestrator"
    )
    parser.add_argument(
        "--simulate-failure",
        action="store_true",
        help="Force Slack provisioning to fail, demonstrating rollback",
    )
    parser.add_argument(
        "--edge-case",
        action="store_true",
        help="Use a hire with ambiguous department, demonstrating escalation",
    )
    args = parser.parse_args()

    # --- Load data ---
    policy = load_role_policy()
    payloads = load_sample_payloads()

    # Select the appropriate payload
    if args.edge_case:
        # Third payload: ambiguous "Growth Engineering" department
        hire = payloads[2]
    elif args.simulate_failure:
        # First payload: normal Engineering hire (failure is injected)
        hire = payloads[0]
    else:
        # Default: normal Engineering hire
        hire = payloads[0]

    emp = hire["employee"]
    name = f"{emp['first_name']} {emp['last_name']}"

    section(f"HeliosHR Onboarding Orchestrator")
    log_info(f"Processing Workday event: {hire['event_id']}")
    log_info(f"New hire: {name} ({emp['employee_id']})")
    log_info(f"Department: {emp['department']}  |  Title: {emp['job_title']}")
    log_info(f"Start date: {emp['start_date']}  |  Type: {emp['employment_type']}")

    audit("webhook_received", "success", {
        "event_id": hire["event_id"],
        "employee_id": emp["employee_id"],
        "department": emp["department"],
    })

    # --- AI role mapping ---
    section("AI Role Mapping (Mock Claude Agent)")
    log_info("Sending hire record + role_policy.json to Claude...")
    mapping = mock_claude_role_mapping(hire, policy)

    log_ok(f"Confidence score: {mapping['confidence']:.0%}")
    log_info(f"Okta groups: {', '.join(mapping['access_profile']['okta_groups'])}")
    log_info(f"Google OU: {mapping['access_profile']['google_workspace_ou']}")
    log_info(f"Slack channels: {', '.join(mapping['access_profile']['slack_channels'])}")
    log_info(f"Jira projects: {', '.join(mapping['access_profile']['jira_projects'])}")
    log_info(f"FreshService: {mapping['access_profile']['freshservice_category']}")

    if mapping["access_profile"]["requires_approval"]:
        log_warn("This department requires manager approval before provisioning")

    audit("ai_role_mapping", "success", {
        "confidence": mapping["confidence"],
        "access_profile": mapping["access_profile"],
    })

    # --- Escalation check ---
    if mapping["confidence"] < CONFIDENCE_THRESHOLD:
        escalate(emp, mapping)
        # Generate a narrative summary even for escalated hires
        audit("narrative_summary", "generated", {
            "summary": (
                f"Onboarding for {name} was escalated to #it-onboarding-review. "
                f"The AI agent could not confidently map department "
                f"'{emp['department']}' to an existing policy (confidence: "
                f"{mapping['confidence']:.0%}). No systems were provisioned. "
                f"Manual review is required before proceeding."
            ),
        })
        write_audit_log(BASE_DIR / "audit_log.json")
        section("Result: Escalated")
        log_warn("Provisioning paused — awaiting manual review")
        return

    # --- Provisioning ---
    results = run_provisioning(
        hire, mapping, simulate_failure=args.simulate_failure
    )

    # --- Welcome message preview ---
    if results.get("_pipeline_status") == "completed":
        section("Welcome Slack Message Preview")
        for line in mapping["welcome_message"].split("\n"):
            print(f"      {line}")

    # --- Narrative summary ---
    if results.get("_pipeline_status") == "completed":
        narrative = (
            f"Onboarding for {name} ({emp['employee_id']}) completed "
            f"successfully. All five provisioning steps (Okta, Google "
            f"Workspace, Slack, Jira, FreshService) finished without error. "
            f"The AI agent mapped the '{emp['department']}' department with "
            f"{mapping['confidence']:.0%} confidence. A welcome message was "
            f"prepared for Slack, and a FreshService onboarding ticket was "
            f"created."
        )
        section("Result: Success")
        log_ok("All provisioning steps completed")
    else:
        failed_at = results.get("_failed_at", "unknown")
        rolled_back = results.get("_rolled_back", [])
        narrative = (
            f"Onboarding for {name} ({emp['employee_id']}) failed at the "
            f"{failed_at} provisioning step. Compensating rollback was "
            f"executed for: {', '.join(rolled_back) if rolled_back else 'none'}. "
            f"Manual intervention is required to complete this onboarding."
        )
        section("Result: Failed")
        log_fail(f"Pipeline failed at {failed_at}")
        if rolled_back:
            log_warn(f"Rolled back: {', '.join(rolled_back)}")

    audit("narrative_summary", "generated", {"summary": narrative})
    log_info(f"Narrative: {narrative}")

    # --- Write audit log ---
    write_audit_log(BASE_DIR / "audit_log.json")


if __name__ == "__main__":
    main()
