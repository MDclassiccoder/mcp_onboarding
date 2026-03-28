# AI Usage Statement

## Tools Used

- **Claude (Anthropic)** — Primary AI tool used throughout this assignment via Claude.ai and Claude Code
- **Claude Code** — Used for generating and iterating on the Python prototype and MCP server code

## How AI Was Applied

**Architecture and design (Claude.ai):** I used Claude as a design partner to explore the system architecture. I described the scenario, constraints, and tech stack, and worked iteratively through design decisions — which systems to provision, where the LLM should sit in the workflow, how to structure the MCP server's tool interface, and how to handle failure modes. Claude generated the Mermaid architecture diagram based on the design we converged on together.

**Technical writeup and executive summary (Claude.ai):** Claude drafted both documents based on the architectural decisions we made together. I reviewed and revised the content to ensure it reflected my own engineering judgment — particularly around the sequential provisioning order, the rollback strategy, and the assumptions section, which I validated against my experience building API integration pipelines.

**Code generation (Claude Code):** I used Claude Code to generate the Python orchestration prototype and MCP server skeleton. I provided the architectural spec and sample payloads, then iterated on the output — adjusting the mock responses to be realistic, refining the Claude prompt templates, and ensuring the error handling paths actually exercised the rollback logic.

**Diagramming (Claude.ai):** The architecture diagram was generated as an SVG visualization within Claude.ai based on our collaborative design session.

## How I Validated and Refined Outputs

- **Architecture review**: I validated every integration point against the actual APIs for Okta, Google Workspace Admin SDK, Slack, Jira, and FreshService to confirm the endpoints and auth methods are accurate
- **Code testing**: I ran the prototype end-to-end to verify the orchestration logic, rollback behavior, and audit log output
- **Writeup editing**: I revised the technical writeup to add specifics from my experience with production API integrations — particularly around idempotency, retry strategies, and credential management patterns I've implemented in Azure Function Apps
- **Executive summary tone**: I rewrote portions to ensure it reads naturally for a non-technical audience, drawing on my experience presenting technical solutions to business stakeholders

## Where I Chose NOT to Use AI

- **Design trade-off decisions**: The choice to use n8n as orchestration (vs. a standalone Python service), the sequential provisioning order (Okta first as identity foundation), and the escalation threshold logic were my own engineering judgment calls based on real-world experience building data pipelines and API integrations
- **Assumption validation**: I verified the Workday webhook, API availability, and rate limit assumptions manually based on my knowledge of these systems
- **MCP SDK choice**: The decision to use the Python `mcp` SDK over FastAPI was a deliberate signal about MCP fluency for this specific role — that's a strategic judgment call, not something I'd delegate to AI
