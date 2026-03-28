# Technical Writeup: AI-Powered Employee Onboarding Automation for HeliosHR

**Author:** Manas Desai  
**Date:** March 2026

---

## Design Decisions

### Why n8n as the orchestration layer

HeliosHR already runs n8n as its primary automation platform. Rather than introducing a new orchestration framework, this design uses n8n as the workflow trigger and routing layer, keeping the operational footprint familiar to the existing IT team. n8n receives the Workday webhook, validates the payload structure, and forwards the hire record to the MCP Onboarding Server for intelligent processing. This separation means n8n handles what it's good at (webhook management, retry scheduling, workflow visibility) while the MCP server handles what requires intelligence (role interpretation, content generation, exception handling).

### Why an MCP server as the integration backbone

The Model Context Protocol (MCP) server is the central nervous system of this design. It exposes five tools — `provision_user`, `check_status`, `rollback_user`, `get_role_policy`, and `escalate_to_it` — that can be called by Claude or any MCP-compatible client. This architectural choice provides several advantages: the onboarding workflow becomes composable (an IT admin could trigger provisioning from Claude Desktop, a Slack bot, or the n8n workflow without duplicating logic), the tool definitions serve as self-documenting API contracts, and the server enforces authentication and authorization at the protocol layer rather than per-integration.

### Why Claude as an active agent — not a chatbot

Claude serves four distinct roles in this workflow, none of which are conversational:

1. **Role-to-access mapping**: Claude reads a structured role policy document (JSON) alongside the Workday hire record and determines which Okta groups, Google Workspace OU, Slack channels, Jira projects, and FreshService category to assign. This replaces brittle hardcoded lookup tables with a system that can handle ambiguous titles, new departments, and cross-functional roles by reasoning against policy rather than matching strings.

2. **Content generation**: Claude writes a personalized welcome Slack message referencing the new hire's name, team, manager, and start date. It also generates the FreshService onboarding ticket description with provisioning details and the new hire's first-week checklist context.

3. **Exception handling**: When the hire record contains ambiguous or missing data (e.g., a department not yet in the policy document, a contractor flagged as FTE, or a title that maps to multiple access profiles), Claude evaluates confidence and either proceeds with the best-match assignment or escalates to the `#it-onboarding-review` Slack channel with a structured summary explaining the ambiguity and its recommendation.

4. **Audit narrative generation**: After provisioning completes, Claude generates a human-readable summary of every action taken, every system provisioned, and any exceptions encountered — stored alongside the structured JSON audit log for compliance review.

---

## Failure Handling, Retries, and Edge Cases

### Sequential provisioning with compensating rollback

Systems are provisioned in dependency order: Okta first (identity is the foundation), then Google Workspace (requires Okta SSO), then Slack, Jira, and FreshService. If any step fails after retries, the workflow executes compensating transactions — rolling back successfully provisioned accounts in reverse order. This prevents orphaned accounts that would need manual cleanup.

### Retry strategy

Each API call uses exponential backoff with jitter (base 2s, max 30s, 3 attempts). Retries are idempotent by design — each provisioning call includes a unique `onboarding_request_id` that downstream systems use for deduplication. If all retries exhaust, the workflow logs the failure, rolls back, and escalates to IT.

### Edge cases handled

- **Duplicate hire records**: The system checks for existing accounts by email before provisioning. If accounts already exist, it logs a warning and skips that system rather than failing.
- **Rehires**: If a previously deactivated employee is rehired, the system reactivates existing accounts rather than creating new ones, preserving historical data.
- **Contractor vs. FTE**: The Workday `worker_type` field determines the access tier. Contractors receive a restricted Okta group with time-bounded access and no Jira project admin privileges.
- **Missing manager data**: If the `manager_email` field is null, Claude flags the record for escalation rather than provisioning without a reporting chain.

---

## Access Governance and Auditability

### Least-privilege service accounts

Each target system integration uses a dedicated OAuth 2.0 service account with the minimum scopes required. The Okta service account can create users and assign groups but cannot modify admin policies. The Slack bot token can invite users and post messages but cannot access message history. Credentials are stored in a secrets manager (e.g., AWS Secrets Manager or HashiCorp Vault) and rotated on a 90-day schedule.

### Immutable audit log

Every action — successful or failed — is recorded in a structured JSON audit log with fields for `timestamp`, `action`, `target_system`, `input_payload`, `response_status`, `response_body`, and `actor` (either "claude-agent" or "human-escalation"). Logs are append-only and written to a durable store (e.g., S3 with versioning enabled or a dedicated audit database). Claude's human-readable narrative is stored alongside each log entry for compliance officers who need to review provisioning decisions without parsing JSON.

### Approval gates

For sensitive roles (InfoSec, Finance, Executive), the workflow pauses before provisioning and routes an approval request to the relevant team lead via Slack. Provisioning only proceeds after explicit approval, with the approver's identity recorded in the audit log.

---

## What I Would Build Next

1. **Offboarding automation**: Mirror the onboarding flow for employee departures — triggered by Workday termination events, deprovisioning across all systems with a 72-hour grace period and manager notification.

2. **Self-service status dashboard**: A lightweight web UI where HR and IT can track onboarding progress in real time, see which systems are provisioned, and intervene on escalations without context-switching to Slack.

3. **Access review automation**: A quarterly workflow that compares each employee's current access grants against their role policy and flags drift (e.g., an engineer who moved to Product but still has engineering Jira admin access).

4. **Onboarding quality scoring**: Use Claude to analyze onboarding completion data (time to first login per system, FreshService ticket resolution time, new hire survey responses) and recommend workflow improvements.

5. **Multi-region support**: Extend the role policy document to include region-specific access requirements (EU data residency, APAC tool preferences) and let Claude factor location into provisioning decisions.

---

## Assumptions

- **Workday supports outbound webhooks** on hire-record activation. If not, a polling-based trigger (n8n cron node querying the Workday API every 15 minutes for new hires) would substitute without changing the downstream architecture.
- **All target systems have REST APIs** with sufficient permissions for programmatic user provisioning. Okta, Google Workspace, Slack, Jira, and FreshService all support this in practice.
- **n8n is self-hosted** with access to internal network resources and the ability to run custom code nodes (for MCP server calls).
- **The role policy document is maintained by IT/HR** and versioned in source control. If this assumption changes (e.g., policies are informal or tribal knowledge), the system would need a policy bootstrapping phase where Claude helps codify existing practices.
- **Claude API access is available** with sufficient rate limits for the expected onboarding volume (~50 new hires/month for a 600-person company).
