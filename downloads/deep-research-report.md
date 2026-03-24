# Deep Research: Locating the 33‑Page Skills Guide and the Alleged Trading‑Bot Example

## Executive summary

A widely shared social claim says a 33‑page “Claude Skills” guide secretly contains a **prediction‑market trading bot** (often paired with ROI claims like “68.4% win rate” and “$300–$1,500/day”). After reviewing the primary candidate document and closely related official materials, I found:

The “33‑page guide” is real and official: it appears to be **“The Complete Guide to Building Skill for Claude”** (PDF, 33 pages) hosted on Anthropic’s resources domain. citeturn1view0

The “hidden trading bot / prediction markets / win rate / daily profit” content is **not present** in that PDF: searches for trading/prediction‑market terms return no matches in the official guide. citeturn2view0turn2view1turn2view3turn30view0turn30view1

The closest official “trading‑adjacent” examples are instead:
- A **portfolio analytics** cookbook notebook that demonstrates Skills‑powered workflows, including **Sharpe ratio** and other risk metrics (but not autonomous trading or win‑rate claims). citeturn24view0turn24view1turn24view3  
- An official open repo of **financial services plugins** (markdown + JSON) containing “trade recommendation” workflows (e.g., **portfolio rebalance**) and partner workflows such as **FX carry trade analysis** that explicitly chains MCP tools and computes risk‑adjusted metrics. citeturn12search0turn27view0turn28view0

No official evaluation artifact supporting the viral quantitative profit claims (68.4% win rate, $300–$1,500/day) was found in Anthropic’s guide, cookbook notebook, or official plugin repos reviewed. Reports in crypto/aggregator news explicitly note that related screenshots appear fabricated rather than extracted from the real document. citeturn10search3turn10search6

In short: you can integrate the **real** official “Skills” patterns (Skills APIs, file creation, code execution, MCP tool chaining, risk metrics), but the **specific “prediction‑market trading bot with verified win rate”** does not appear to exist as an official embedded example in the 33‑page guide.

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["The Complete Guide to Building Skill for Claude Anthropic PDF cover","Claude Agent Skills progressive disclosure diagram","Claude LSEG plugin FX carry trade screenshot","Claude wealth management plugin screenshot"],"num_per_query":1}

## Official sources located and how to retrieve them

The official “33‑page” document most consistently linked in the viral posts is hosted on an Anthropic resource CDN and is titled:

**“The Complete Guide to Building Skill for Claude” (PDF, 33 pages)** citeturn1view0

This PDF is a formal guide describing how to design, package, and test “Skills” (filesystem‑based bundles of instructions/resources), including tactical guidance on SKILL.md structure, YAML frontmatter, and workflow design. citeturn8view1turn8view3

In parallel, Anthropic maintains canonical “Skills” documentation and related materials in:
- **Claude API Docs: Agent Skills overview** (explains what Skills are, file structure, security considerations, and how to use Skills across surfaces). citeturn11view0  
- **Engineering blog: Equipping agents… with Agent Skills** (conceptual explanation; uses Skills for PDF manipulation as a concrete example and discusses progressive disclosure). citeturn22view0  
- **Claude Cookbook: “Claude Skills for financial applications”** (an official notebook rendered as a web page, showing end‑to‑end Skills API calls and file‑generating workflows including portfolio analytics). citeturn24view0turn24view1turn24view3  
- **Official GitHub repos for plugins and Skills ecosystems** (financial workflows, plugin structure, partner tools). citeturn12search0turn12search2  

## What’s actually inside the 33‑page guide and whether the trading “bot” is in it

The 33‑page PDF focuses on:
- Planning and defining use cases and success criteria for Skills. citeturn8view1turn8view2  
- Technical requirements (directory layout, naming conventions, YAML frontmatter expectations). citeturn8view3  
- Authoring guidance for Skills (what instructions go where, progressive disclosure patterns, etc.). citeturn1view0turn8view3

Crucially, the viral “buried trading bot” claim does not align with the PDF’s accessible text content:
- Searching the PDF text for “trade”, “trading”, or “prediction” yields **no matches**. citeturn2view0turn2view1turn2view3  
- Searching for “2800” / “2,800” likewise yields **no matches**. citeturn30view0turn30view1  

This is consistent with third‑party “fact‑check” style writeups noting that screenshots circulating alongside the claim do not seem to reflect the real PDF content, and may be fabricated. citeturn10search3turn10search6

## Extracted trading-adjacent examples from official materials

Because the “prediction‑market trading bot” content is not present in the official 33‑page PDF, the most relevant *official* substitutes are:

### Portfolio analytics workflow with Sharpe ratio in the official cookbook

The official cookbook entry “Claude Skills for financial applications” demonstrates Skills being used to create financial dashboards, portfolio analytics, and reporting workflows. citeturn24view0

It includes:
- A portfolio dataset with **holdings**, and “performance metrics” including **Sharpe ratio** (and other risk indicators). citeturn30view4turn24view3  
- A portfolio analysis Excel workflow (“Portfolio Overview”, “Sector Analysis & Risk”) that explicitly references Sharpe ratio, beta, standard deviation, VaR, and drawdown fields in the prompt. citeturn20view6  
- An investment committee deck prompt that includes “Sharpe Ratio” and risk metrics as slide content. citeturn24view3turn20view0  

This is “trading‑adjacent” in the sense that it produces **rebalancing recommendations** and risk dashboards; it is not an autonomous bot and does not contain win‑rate claims. citeturn24view3turn20view1

### Portfolio rebalance “trade recommendation” skill in the official financial-services plugins repo

The official repo “Claude for Financial Services Plugins” includes workflows for investment banking, equity research, private equity, and wealth management. citeturn12search0

One included Skill (“Portfolio Rebalance”) is explicitly about generating **rebalancing trade recommendations**, with tax and wash sale considerations and a structured “Trade List” output. citeturn27view0

It outlines:
- Inputs needed for current state (account types; holdings; cost basis; gains/losses). citeturn27view0  
- Drift analysis vs. targets and rebalancing bands. citeturn27view0  
- Trade generation logic and tax‑aware rules (tax‑advantaged first, avoid short‑term gains, harvest losses, wash sale constraints). citeturn27view0  

Again: this is a “decision support” Skill rather than an automated trading bot with performance claims.

### FX carry trade analysis Skill with explicit MCP tool chaining

In the same official plugins ecosystem, the partner‑built LSEG module includes a Skill “FX Carry Trade” that:
- Enumerates **MCP tools** like `fx_spot_price`, `fx_forward_price`, `fx_forward_curve`, `fx_vol_surface`, and a historical pricing tool. citeturn28view0  
- Defines a tool‑chaining workflow to compute **annualized carry**, map carry curves, compute **carry‑to‑vol**, and synthesize a recommendation. citeturn28view0  
- Specifies output tables and recommendation fields (direction, tenor, carry‑to‑vol ratio, risks, conviction). citeturn28view0  

This is the closest thing in official materials to a “trading workflow” that resembles systematic decision logic with tool integration.

## Exact configuration, dependencies, API calls, data sources, and limits found in the official examples

### Dependencies and runtime assumptions (cookbook notebook)

The cookbook “financial applications” notebook is explicit about environment and dependencies:
- **Anthropic Python SDK** usage (import `Anthropic`), `pandas`, `python-dotenv`, filesystem helpers, and a `.env`‑configured API key. citeturn24view0turn24view1  
- It sets `MODEL = "claude-sonnet-4-6"`. citeturn24view0  
- It calls `client.beta.messages.create(...)` with:
  - `container={"skills": skills}`  
  - `tools=[{"type": "code_execution_20250825", "name": "code_execution"}]`  
  - `betas=["code-execution-2025-08-25","files-api-2025-04-14","skills-2025-10-02"]` citeturn24view1  

This gives you concrete levers for a faithful reproduction:
- The Skills API “container skills” mechanism. citeturn24view1  
- The beta feature gating tokens (code execution, files API, skills API). citeturn24view1  

### Model IDs and pricing

The official models list and pricing docs identify:
- API model IDs such as `claude-sonnet-4-6` and context window characteristics. citeturn32search1  
- A canonical pricing page in the API docs that lists model pricing and related pricing categories (including prompt caching and batch processing details). citeturn32search0turn33search10  

For cost modeling, the headline Sonnet 4.6 token pricing referenced in official docs is **$3 / MTok input** and **$15 / MTok output**. citeturn32search4turn32search3turn32search2

### Code execution tool pricing

For the code execution tool, the API capabilities announcement states:
- **50 free hours per day** of code execution tool usage per organization, then **$0.05 per hour per container** thereafter. citeturn34view0

### Rate limits and Files API constraints

The API rate limits documentation explains:
- Two kinds of org limits: **spend limits** and **rate limits**; rate limits apply in RPM and token‑per‑minute measures (input/output), with 429 errors and `retry-after` headers. citeturn35view0turn35view2  
- Standard tier monthly ceilings (Tier 1–4) and how tier advancement works. citeturn35view0  

For Files API specifically, the Files documentation notes beta‑period rate limiting of approximately **100 file‑related requests per minute**. citeturn33search12

### Tool wrappers and data sources for the “trading‑adjacent” skills

For the LSEG carry trade skill, the “tool wrapper” layer is MCP:
- The Skill itself documents the tool surface and expected outputs (spot, forwards, curves, vol surfaces, historical). citeturn28view0  
- The underlying live market data sources are provided via the connected MCP environment (as implied by the plugin’s positioning and tool naming), not by the Skill alone. citeturn26search0turn28view0  

For the wealth management “portfolio rebalance” Skill:
- It is primarily methodology and templated outputs; data inputs come from the user’s portfolio/IPS context (or from firm data sources if connected via MCP in a production setting). citeturn27view0turn12search0  

### Authentication and “scopes”

Across the official cookbook and API docs:
- “Skills for financial applications” uses `ANTHROPIC_API_KEY` from environment variables, consistent with the standard API authorization model. citeturn24view0turn33search1  
- MCP‑connected data providers (e.g., LSEG) typically imply separate partner authentication at the connector/server layer (keys, OAuth, entitlements), but those credentials are not embedded in the Skills; they live in the MCP server configuration and provider contracts. This is consistent with the plugin architecture described as “skills + connectors” rather than standalone code. citeturn12search0turn34view0  

## Verification status of the viral performance claims

### Claim: “68.4% win rate” and “$300–$1,500/day”

I found **no official evaluation appendix, backtest report, or reproducibility notes** in:
- The 33‑page official Skills PDF citeturn1view0turn2view0turn2view1turn2view3  
- The official financial applications notebook citeturn24view0turn20view1  
- The official financial services plugin repos examined (the extracted Skills describe workflows and metrics, but do not publish win‑rate P&L claims). citeturn12search0turn27view0turn28view0  

Multiple secondary writeups about the viral episode explicitly state that screenshots “seemed fabricated” and didn’t match the actual PDF contents, which aligns with the direct text‑search results above. citeturn10search3turn10search6

### What “evaluation” exists in official materials

Official materials do include:
- Guidance for defining success criteria and quantitative/qualitative metrics for Skills (e.g., trigger rates, tool calls, failure rates). citeturn8view2turn11view0  
- Concrete finance metrics in examples (e.g., **Sharpe ratio** in portfolio workflows; **carry‑to‑vol** in FX workflows). citeturn24view3turn28view0  

They do not provide trading profitability validation. If you need win‑rate or Sharpe for a strategy, you’ll need to build a **reproducible backtest and audit trail** external to Claude/Skills, then integrate it as a tool or evaluation harness.

## Integration-ready blueprint for your AI system

This section assumes you want to integrate (a) Skills‑style “procedural bundles” and (b) finance/trading decision support patterns, while also providing a safe path toward any eventual “bot” automation.

### Implementation checklist

Establish the “Skills” substrate:
- Implement a Skills loader with **YAML frontmatter discovery** and **progressive disclosure** semantics (metadata always available; load full SKILL.md only when triggered), consistent with the Agent Skills design described in official docs. citeturn11view0turn22view0  
- Enforce a strict trust model: only load Skills from vetted sources; treat Skill content as executable policy. Official docs explicitly warn that Skills can be malicious because they can direct tool invocation and code execution. citeturn11view0turn35view0  

Reproduce the official “financial workflow” API call pattern:
- Match the cookbook’s request shape using `client.beta.messages.create` (or your equivalent), including:
  - `model="claude-sonnet-4-6"`  
  - `container={"skills": [...]}`  
  - `tools=[{"type":"code_execution_20250825","name":"code_execution"}]`  
  - beta headers: `code-execution-2025-08-25`, `files-api-2025-04-14`, `skills-2025-10-02` citeturn24view1turn24view0  

Implement finance tools as “read‑only first”:
- For market data ingestion, mirror the LSEG carry trade pattern: separate “fetch pricing data” tools from “compute risk metrics” logic. citeturn28view0  
- Start with **analysis‑only** output (recommendations, risk metrics, trade suggestions) rather than execution.

Add trade execution only behind hard gates:
- Introduce a dedicated order‑execution tool that requires:
  - deterministic schema validation (symbol, side, quantity, price constraints, time‑in‑force)  
  - policy checks (account permissions, max position sizing, restricted lists)  
  - a human approval step for any live order (at least until you have extensive safety evidence).

### Security, ethical, and legal risk surface

High-risk categories you should explicitly mitigate:

Tool/Skill prompt injection and unintended actions:
- Skills can instruct the agent to run code or invoke tools in harmful ways; this is explicitly called out in the Agent Skills security guidance. citeturn11view0turn22view0  
- Mitigation: allow‑list tools per Skill; sandbox code execution; log every tool call; require explicit user approval for state‑changing actions.

Financial compliance and consumer harm:
- “Trading bots” can create significant user harm (losses, unsuitable recommendations). Treat outputs as decision support, not advice, and implement suitability/risk profiling if you are serving retail users.

Market manipulation / prohibited behavior:
- Enforce rules against wash trading, spoofing, coordinated manipulation, and any instruction to evade platform rules. Build monitoring and anomaly detection in execution layers.

Data licensing and entitlements:
- Partner data sources (institutional market feeds, vol surfaces) often have contractual restrictions; the tool layer must enforce entitlements rather than letting the model “request everything.”

### Compute and cost estimates

A practical cost model for the official patterns you’re integrating:

Token costs (Sonnet 4.6 baseline):
- Official docs cite **$3 / MTok input** and **$15 / MTok output** for Sonnet 4.6. citeturn32search4turn32search2turn32search3  
- Expected per-request payout depends on prompt length, tool outputs, and artifact generation size. The portfolio notebook uses `max_tokens=4096` in the sample helper, which caps output tokens but not input growth. citeturn24view1  

Code execution costs:
- The code execution tool is metered by container-hours: **50 free hours/day/org**, then **$0.05 per hour per container**. citeturn34view0  
- For trading analytics, you can reduce code execution usage by pushing numeric computation into deterministic microservices and reserving code execution for ad‑hoc analysis jobs and artifact generation.

Rate-limit planning:
- The API enforces RPM and token/min limits by tier; bursts can be rate-limited even if average usage seems fine. citeturn35view0turn35view2  
- File operations can be separately constrained (Files API ~100 requests/min in beta). citeturn33search12  

### A consolidated comparison table of the official “examples” (inputs/outputs/prompts/code)

| Official artifact | Primary purpose | Inputs | Outputs | Prompts / instructions style | Tooling / APIs |
|---|---|---|---|---|---|
| “The Complete Guide to Building Skill for Claude” (33‑page PDF) | Skill authoring guidance | Human-authored Skill workflows | None directly (documentation) | Methodology, templates, file structure guidance citeturn1view0turn8view3 | N/A |
| Cookbook: “Claude Skills for financial applications” | Generate dashboards + portfolio analytics | CSV/JSON sample datasets (financial statements, portfolio holdings, quarterly metrics) citeturn30view4turn24view0 | XLSX + PPTX + PDF artifacts; portfolio slides include Sharpe ratio and risk metrics citeturn24view3turn20view0 | Long-form “create a workbook/deck with…” prompts embedding numeric fields citeturn24view3turn20view6 | `client.beta.messages.create` with Skills container + code execution tool + beta flags citeturn24view1 |
| Financial services plugins: “Portfolio Rebalance” Skill | Rebalancing trade recommendations | Portfolio + IPS targets + account types + tax context citeturn27view0 | Drift analysis table + “Trade List” template + tax impact notes citeturn27view0 | Prescriptive workflow steps and structured tables citeturn27view0 | Skill-only methodology; execution depends on your MCP / data plumbing citeturn12search0 |
| Partner Skill: “FX Carry Trade” (LSEG) | Systematic carry analysis (risk-adjusted) | FX spot, forwards, curve, vol surface, history via MCP tools citeturn28view0turn26search0 | Carry profile tables + carry-to-vol + trade recommendation fields citeturn28view0 | Explicit tool-chaining workflow, deterministic computations done by user/agent citeturn28view0 | MCP tool calls (`fx_spot_price`, `fx_forward_curve`, etc.) citeturn28view0 |

### Agent decision-flow timeline (Mermaid)

```mermaid
flowchart TD
  A[User intent arrives] --> B{Skill trigger?}
  B -->|No| C[General assistant behavior]
  B -->|Yes| D[Load Skill metadata]
  D --> E[Read SKILL.md + referenced files]
  E --> F{Risk class?}
  F -->|Low/medium| G[Plan tool calls]
  F -->|High-risk (trading/execution)| H[Enable stricter policy gates]

  G --> I[Call read-only tools (market data, portfolio, news)]
  H --> I

  I --> J[Compute metrics]
  J --> K[Generate recommendation + rationale]
  K --> L{Execution requested?}
  L -->|No| M[Deliver report/artifacts]
  L -->|Yes| N[Pre-trade checks: limits, compliance, schema]
  N --> O{Human approval?}
  O -->|Denied| M
  O -->|Approved| P[Place order via broker tool]
  P --> Q[Log decision + tool traces + state]
  Q --> R[Post-trade monitoring + evaluation harness]
  R --> S[Update strategy memory / dashboards]
```

### Suggested modifications to fit production systems

To evolve from decision-support Skills toward a safe “trading agent,” the most production-aligned path is to treat Claude as an orchestrator and narrative generator, while moving execution-critical logic into deterministic services:

Replace “trading bot claims” with auditable evaluation:
- Build a backtest harness that outputs:
  - trade list + timestamps + signal features  
  - portfolio NAV curve  
  - metrics (Sharpe/Sortino, max drawdown, turnover, slippage assumptions)  
- Have the model **read** those outputs and generate explanations/reports, rather than compute performance claims itself.

Enforce separation of concerns:
- MCP/tools: data retrieval only  
- Deterministic service: signal calculation + portfolio construction + order sizing  
- Model: marshals tools, explains, drafts IC memos, generates artifacts, produces human-readable summaries

Harden safety:
- Adopt strict tool allow-lists per Skill and require explicit approvals for risky commands, aligning with the official warning that Skills can be malicious if untrusted. citeturn11view0turn22view0  
- Implement rate-limit aware retries and circuit breakers, consistent with the platform’s explicit rate-limit behavior. citeturn35view0turn33search18  

If you want me to narrow this further to a specific “target integration” (e.g., your agent framework, what tool protocol you use, whether you need simulation-only vs. live execution), I can translate the extracted official patterns into a concrete module layout (Skill bundles + tools + eval harness) while preserving traceability to the official sources above.