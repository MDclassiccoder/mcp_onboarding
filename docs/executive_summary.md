# Executive Summary: Automating Employee Onboarding at HeliosHR

**Prepared for:** Head of People Operations  
**Prepared by:** Manas Desai  
**Date:** March 2026

---

## What This System Does

Today, when a new hire is entered into Workday, IT receives a Slack message and manually creates accounts across five different systems — Okta, Google Workspace, Slack, Jira, and FreshService. This takes 3–5 business days and frequently results in new hires starting their first day without access to the tools they need.

The proposed system eliminates this manual process entirely. The moment a new hire record is activated in Workday, the system automatically provisions all of their accounts — with the right permissions for their role, department, and location — in minutes rather than days. An AI agent (Claude) reads each hire record, determines exactly what access the person needs based on company policy, creates all accounts, sends a personalized welcome message in Slack, and opens an onboarding ticket in FreshService with their first-week checklist.

When the system encounters something it's unsure about — like a new department title it hasn't seen before, or a role that could map to multiple access levels — it pauses and asks a human IT team member to review, rather than guessing.

---

## What This Improves

**Speed**: Onboarding drops from 3–5 business days to under 30 minutes. New hires have working accounts on day one.

**Accuracy**: Automated provisioning eliminates copy-paste errors, forgotten systems, and inconsistent access levels. Every new hire gets exactly the access their role requires — no more, no less.

**IT capacity**: The IT team reclaims an estimated 8–12 hours per week currently spent on manual provisioning, freeing them for higher-value work.

**Compliance**: Every provisioning action is logged with a timestamp, what was done, and why. Auditors can review a complete, human-readable trail for any employee's onboarding within seconds.

**How we'd measure success**: Time from Workday activation to full provisioning (target: <30 min), provisioning error rate (target: <2%), IT hours saved per month, and new hire satisfaction survey scores on "day one readiness."

---

## Risks and Limitations

**API dependencies**: If any target system's API is down (e.g., Okta has an outage), the system will retry automatically and alert IT. It will not leave accounts partially provisioned — if one system fails, it rolls everything back cleanly.

**Edge cases still need humans**: Unusual situations — like a hire into a brand-new department, an international transfer with region-specific access needs, or a sensitive role like InfoSec — will be routed to IT for manual review. The system is designed to handle the 90% of onboardings that are straightforward and escalate the 10% that aren't.

**Policy maintenance**: The system's intelligence comes from a role-to-access policy document that maps departments and titles to the right permissions. This document needs to be updated when HeliosHR adds new teams, tools, or access tiers. This is a lightweight task but requires ongoing ownership.

**No retroactive cleanup**: This system handles new onboardings going forward. Existing employees with inconsistent access from the old manual process would need a separate access review initiative.

---

## What You Need to Know to Feel Confident

**Human oversight is built in.** The system doesn't operate as a black box. Every action it takes is logged and explainable. For sensitive roles, it explicitly waits for human approval before proceeding. IT retains full control and can pause, override, or roll back any onboarding at any time.

**Rollout would be gradual.** We'd start by running the system in "shadow mode" alongside the existing manual process for 2–4 weeks — it provisions accounts but IT reviews each one before the new hire is notified. Once confidence is established, we shift to full automation with IT monitoring the dashboard.

**This doesn't replace IT — it amplifies them.** The team still owns the onboarding process, the access policies, and the exception handling. The system handles the repetitive execution so they can focus on the decisions that actually require human judgment.
