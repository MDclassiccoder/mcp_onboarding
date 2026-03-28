# HeliosHR AI-Powered Onboarding Automation

A prototype demonstrating AI-driven employee onboarding orchestration. The system processes Workday webhook events and provisions accounts across five SaaS platforms (Okta, Google Workspace, Slack, Jira, FreshService) using Claude AI for intelligent role-to-access mapping.

All external API calls and Claude AI calls are **mocked** — no API keys or live services are needed.

## Quick Start

```bash
# No external dependencies needed for the orchestrator
python onboarding_orchestrator.py
```

### Run Modes

**Normal onboarding** — provisions a Senior Backend Engineer in the Engineering department:
```bash
python onboarding_orchestrator.py
```

**Simulate failure** — forces Slack provisioning to fail, triggering compensating rollback of Google Workspace and Okta:
```bash
python onboarding_orchestrator.py --simulate-failure
```

**Edge case** — uses a hire with department "Growth Engineering" (not in policy), causing the AI to return low confidence and trigger escalation to #it-onboarding-review:
```bash
python onboarding_orchestrator.py --edge-case
```

### What to Expect

| Flag | Behavior |
|------|----------|
| *(none)* | All 5 provisioning steps succeed. Welcome message and FreshService ticket are generated. Audit log written. |
| `--simulate-failure` | Okta and Google Workspace succeed, Slack fails. Rollback is triggered: Google Workspace suspended, Okta deactivated. |
| `--edge-case` | AI maps "Growth Engineering" to Engineering with 62% confidence (below 80% threshold). Escalation message is generated. No provisioning occurs. |

After each run, check `audit_log.json` for the full structured audit trail.

## MCP Server

The MCP server exposes the same orchestration logic as tools that an AI agent can invoke.

### Setup

```bash
pip install mcp
```

### Start the Server

```bash
python onboarding_mcp_server.py
```

The server uses **stdio transport** and exposes five tools:

| Tool | Description |
|------|-------------|
| `provision_user(hire_record)` | Run the full provisioning workflow |
| `check_provisioning_status(employee_id)` | Query current provisioning state |
| `rollback_user(employee_id)` | Roll back all provisioned accounts |
| `get_role_policy(department)` | Look up access mapping for a department |
| `escalate_to_it(employee_id, reason)` | Log an escalation to #it-onboarding-review |

### Connect from Claude Desktop

Add to your Claude Desktop MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "helioshr-onboarding": {
      "command": "python",
      "args": ["path/to/onboarding_mcp_server.py"]
    }
  }
}
```

## Project Structure

```
helioshr-onboarding/
├── onboarding_orchestrator.py   # Main orchestration script (CLI)
├── onboarding_mcp_server.py     # MCP server exposing tools
├── role_policy.json             # Department-to-access policy mappings
├── sample_payloads.json         # Sample Workday webhook payloads
├── requirements.txt             # Python dependencies (mcp)
├── audit_log.json               # Generated after each run
└── README.md
```

## Architecture

```
Workday Webhook ──► Orchestrator ──► Claude AI (mock) ──► Role Mapping
                         │
                         ├──► Okta (create user + assign groups)
                         ├──► Google Workspace (create account in OU)
                         ├──► Slack (invite + join channels)
                         ├──► Jira (create user + assign projects)
                         └──► FreshService (create onboarding ticket)
                         │
                    On Failure: Compensating Rollback
                    Low Confidence: Escalation to IT
```
