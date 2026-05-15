# RivalSearchMCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
![MCP Server](https://img.shields.io/badge/MCP-Server-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white&style=for-the-badge)
![FastMCP](https://img.shields.io/badge/FastMCP-3.2+-green?style=for-the-badge)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin&style=for-the-badge)](https://www.linkedin.com/in/damion-rashford)

[![CI](https://github.com/damionrashford/RivalSearchMCP/actions/workflows/ci.yml/badge.svg)](https://github.com/damionrashford/RivalSearchMCP/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/damionrashford/RivalSearchMCP/branch/main/graph/badge.svg)](https://codecov.io/gh/damionrashford/RivalSearchMCP)
[![Reviewed by Claude](https://img.shields.io/badge/Reviewed_by-Claude-D97757?logo=anthropic&logoColor=white)](https://github.com/anthropics/claude-code-action)
[![Releases](https://img.shields.io/github/v/release/damionrashford/RivalSearchMCP?include_prereleases&label=latest&color=8957e5)](https://github.com/damionrashford/RivalSearchMCP/releases)

![GitHub Stars](https://img.shields.io/github/stars/damionrashford/RivalSearchMCP?style=social)
![GitHub Forks](https://img.shields.io/github/forks/damionrashford/RivalSearchMCP?style=social)
![GitHub Issues](https://img.shields.io/github/issues/damionrashford/RivalSearchMCP?style=social)
![Last Commit](https://img.shields.io/github/last-commit/damionrashford/RivalSearchMCP?style=social)
![Visitor Count](https://visitor-badge.laobi.icu/badge?page_id=damionrashford.RivalSearchMCP)

**Deterministic research MCP server — web + social + academic + news + code + docs, all in one place. No API keys, no in-server LLM, structured outputs for agent chaining.**

> 🆓 **100% Free & Open Source** — No API keys, no subscriptions, no rate limits. Just add one URL and go.

## What It Does

RivalSearchMCP is a FastMCP 3.x server exposing **10 specialized tools** that search, fetch, score, and compare information across:

- **5 web search engines** (DuckDuckGo, Bing, Yahoo, Mojeek, Wikipedia) — concurrent, deduplicated, with TLS-fingerprint-safe fetches via Scrapling
- **9 social platforms** (Reddit, Hacker News, Stack Overflow, Dev.to, Medium, Product Hunt, Bluesky, Lobste.rs, Lemmy) — no authentication
- **5 news sources** (Google News, Bing News, The Guardian, GDELT, DuckDuckGo News) — with time-range filtering
- **5 academic databases** (OpenAlex, CrossRef, arXiv, PubMed, Europe PMC) + **4 dataset hubs** (Kaggle, HuggingFace, Dataverse, Zenodo)
- **GitHub repositories** with built-in rate limiting
- **Documents** (PDF, Word, text, images) with OCR for images
- **Website traversal** with research, docs, and mapping modes

**No LLM runs inside the server.** Every tool returns deterministic, auditable output — the caller's model does the synthesis. Tools that benefit from structured output (`content_operations score`, `find_conflicts`) return `ToolResult` with both a human-readable markdown rendering and a parseable `structuredContent` dict, so agents can chain tool outputs without regex-parsing prose.

## ✅ Why It's Useful

- **One connection, ten capabilities** — no need to wire up separate MCP servers per source
- **Auto-quality scoring** — every result carries a tier/freshness/corroboration/citation score (0-100) and every multi-result response carries an aggregate confidence signal
- **Conflict detection** — `content_operations find_conflicts` surfaces numeric, date, and polarity disagreements across sources as a first-class signal instead of averaging them away
- **Persistent research workspaces** — `research_memory` lets an agent iteratively build up a session across calls with findings, notes, and dedup by URL
- **Entity profiles** — `research_topic(mode="entity")` fans out to 8 sources in parallel and returns a unified report with confidence
- **Production hygiene** — per-tool timeouts, rate limiting (100 req/min/session), response-size caps, error masking, middleware-level observability

## 💡 Example Query

Once connected, try asking your AI assistant:

> "Use RivalSearchMCP to research FastAPI vs Django. Run `research_topic` in topic mode on both, aggregate the news, check Reddit and Hacker News for recent discussions, search GitHub for activity, and look for academic papers. Score the top sources, find any conflicts between them, and save the findings to a named research session."

## 📦 How to Get Started

RivalSearchMCP runs as a **remote MCP server** hosted on FastMCP. Just follow the steps below to install, and go.

### Connect to Live Server

[![Install MCP Server](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/en-US/install-mcp?name=RivalSearchMCP&config=eyJ1cmwiOiJodHRwczovL1JpdmFsU2VhcmNoTUNQLmZhc3RtY3AuYXBwL21jcCJ9)

Or add this configuration manually:

**For Cursor:**
```json
{
  "mcpServers": {
    "RivalSearchMCP": {
      "url": "https://RivalSearchMCP.fastmcp.app/mcp"
    }
  }
}
```

**For Claude Desktop:**
- Go to Settings → Add Remote Server
- Enter URL: `https://RivalSearchMCP.fastmcp.app/mcp`

**For VS Code:**
- Add the above JSON to your `.vscode/mcp.json` file

**For Claude Code:**
- Use the built-in MCP management: `claude mcp add RivalSearchMCP --url https://RivalSearchMCP.fastmcp.app/mcp`

### Local Installation with FastMCP CLI

**Prerequisites:**
```bash
# Install UV (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install FastMCP CLI (optional but recommended)
uv tool install fastmcp
```

**Method 1: One-Command Install (Easiest)**
```bash
# Clone repository
git clone https://github.com/damionrashford/RivalSearchMCP.git
cd RivalSearchMCP

# Install directly to your MCP client:
fastmcp install claude-desktop server.py   # For Claude Desktop
fastmcp install cursor server.py           # For Cursor
fastmcp install claude-code server.py      # For Claude Code
```

**Method 2: Quick Run (No Installation)**
```bash
git clone https://github.com/damionrashford/RivalSearchMCP.git
cd RivalSearchMCP

# Run directly with FastMCP CLI
fastmcp run server.py  # Auto-detects entrypoint, uses STDIO

# Or run in HTTP mode for testing
fastmcp run server.py --transport http --port 8000
```

**Method 3: Development with Inspector**
```bash
# Run with MCP Inspector for testing
fastmcp dev server.py
```

**Method 4: Manual UV Setup**
```bash
git clone https://github.com/damionrashford/RivalSearchMCP.git
cd RivalSearchMCP
uv sync

# Add to Claude Desktop or Cursor config:
{
  "RivalSearchMCP": {
    "command": "uv",
    "args": [
      "--directory",
      "/full/path/to/RivalSearchMCP",
      "run",
      "python",
      "server.py"
    ]
  }
}
```

## 🛠 Available Tools (10 Total)

Every tool carries `ToolAnnotations` (`readOnlyHint`, `openWorldHint`, `destructiveHint`, `idempotentHint`) so MCP clients like Claude and ChatGPT can skip confirmation prompts where safe. Every tool has a `timeout=` ceiling so a hung source can't stall the client.

### Search & Discovery (5 tools)
- **`web_search`** — concurrent multi-engine search across DuckDuckGo, Bing, Yahoo, Mojeek, and Wikipedia. Scrapling-backed TLS fingerprinting bypasses Cloudflare/Akamai fronting. Per-engine failures don't block the others.
- **`social_search`** — 9 platforms: Reddit, Hacker News, Stack Overflow, Dev.to, Medium, Product Hunt, Bluesky, Lobste.rs, Lemmy. No authentication.
- **`news_aggregation`** — 5 sources: Google News, Bing News, The Guardian, GDELT, DuckDuckGo News. Accepts `time_range` (day/week/month/anytime).
- **`github_search`** — repository search with built-in rate limiting (60/hr unauthenticated), optional README inclusion.
- **`map_website`** — traverse a site in `research`, `docs`, or `map` mode; returns per-page quality scores and an aggregate confidence signal.

### Content Analysis (3 tools)
- **`content_operations`** — one tool, six operations: `retrieve`, `stream`, `analyze`, `extract`, `score`, `find_conflicts`.
  - `score` rates URLs on tier / freshness / corroboration / citations (0-100) and returns both markdown + structured JSON.
  - `find_conflicts` compares 2-10 sources for numeric / date / polarity disagreements with confidence weights.
- **`research_topic`** — two modes: `topic` (search + fetch + relevance-ranked key findings) and `entity` (unified cross-source profile of a named entity, fanning out to web / news / GitHub / social / academic in parallel). Optional `session_id` auto-saves findings to research memory.
- **`document_analysis`** — extract text from PDF, Word, plain text, and images. Images use EasyOCR (lazy-loaded; no setup). 50 MB cap.

### Research Workflow (2 tools)
- **`scientific_research`** — academic paper and dataset search. 5 paper providers (OpenAlex, CrossRef, arXiv, PubMed, Europe PMC) and 4 dataset hubs (Kaggle, HuggingFace, Dataverse, Zenodo).
- **`research_memory`** — persistent research workspaces with `start` / `add` / `get` / `list` / `delete`. Sessions survive reconnects; with `RESEARCH_MEMORY_DIR` set, they also survive server restarts. Dedupes findings by URL automatically.

## Agent Skills

RivalSearchMCP ships with a **Claude Code Agent Skill** — a self-contained CLI that lets AI agents use all 10 tools without MCP configuration.

### Use as a Claude Code Skill

Copy the skill into your Claude Code skills directory:
```bash
# Project-level (available when working in this repo)
cp -r skills/rival-search-mcp .claude/skills/

# Global (available in all projects)
cp -r skills/rival-search-mcp ~/.claude/skills/
```

Claude will automatically discover the skill and use the CLI when you ask for web research, competitor analysis, or content discovery.

### Use the CLI directly

The CLI is self-contained with inline dependencies — just run with `uv`:
```bash
uv run skills/rival-search-mcp/scripts/cli.py call-tool web_search --query "your query"
uv run skills/rival-search-mcp/scripts/cli.py call-tool social_search --query "AI agents" --platforms reddit
uv run skills/rival-search-mcp/scripts/cli.py call-tool news_aggregation --query "tech news" --time-range week
uv run skills/rival-search-mcp/scripts/cli.py list-tools
```

### Skill structure
```
skills/rival-search-mcp/
├── SKILL.md              # Agent instructions (auto-loaded by Claude Code)
├── scripts/
│   └── cli.py            # Standalone CLI with all 10 tools
└── resources/
    ├── search.md         # web_search, social_search, news_aggregation, github_search, map_website
    ├── content.md        # content_operations, document_analysis
    └── research.md       # research_topic, scientific_research, research_memory
```

## ⚡ Key Features

- **Multi-Engine Search**: 5 search engines (DuckDuckGo, Bing, Yahoo, Mojeek, Wikipedia) with TLS-fingerprint-safe fetches via Scrapling
- **9-Platform Social Research**: Reddit, Hacker News, Stack Overflow, Dev.to, Medium, Product Hunt, Bluesky, Lobste.rs, Lemmy
- **5-Source News Aggregation**: Google News, Bing News, The Guardian, GDELT, DuckDuckGo News — with time-range filtering
- **5 Academic Databases + 4 Dataset Hubs**: OpenAlex, CrossRef, arXiv, PubMed, Europe PMC + Kaggle, HuggingFace, Dataverse, Zenodo
- **Deterministic Output**: no LLM runs inside the server; callers' models do the synthesis
- **Structured `ToolResult`**: `content_operations score` and `find_conflicts` return both markdown (for humans) and parseable JSON (for agent chaining)
- **Auto-Quality Scoring**: every multi-result tool attaches per-item quality (0-100) and an aggregate confidence signal
- **Conflict Detection**: finds numeric/date/polarity disagreements across sources with confidence weights
- **Persistent Research Memory**: named workspaces with auto-dedup, survive server restarts when `RESEARCH_MEMORY_DIR` is set
- **Document Analysis**: PDF / Word / text / images (images via EasyOCR, auto-downloaded)
- **Production Hygiene**: per-tool timeouts, sliding-window rate limiting, response-size caps, error masking, FastMCP 3.x middleware stack
- **Zero Authentication**: every tool works without API keys or setup.

## 💬 FAQ

<details>
<summary><strong>Is RivalSearchMCP really free?</strong></summary>

Yes! RivalSearchMCP is 100% free and open source under the MIT License. There are no API costs, no subscriptions, and no rate limits. You can use the hosted server or run it locally.
</details>

<details>
<summary><strong>Do I need API keys?</strong></summary>

No. RivalSearchMCP works completely without any API keys, authentication, or configuration. Just add the URL and use all 10 tools immediately.
</details>

<details>
<summary><strong>What MCP clients are supported?</strong></summary>

RivalSearchMCP works with any MCP-compatible client including Claude Desktop, Cursor, VS Code, and Claude Code.
</details>

<details>
<summary><strong>Can I self-host this?</strong></summary>

Yes. Clone the repo, run `uv sync --extra dev`, then `fastmcp run` (stdio) or `fastmcp run --transport http --host 0.0.0.0 --port 8000` (HTTP). Full instructions are in the Getting Started section above.
</details>

<details>
<summary><strong>Why is there no in-server LLM / research agent?</strong></summary>

Deliberately. The server returns deterministic, auditable output so the caller's model can reason over it — a consistent machine can't hallucinate the way a synthesizing one can. If you want an autonomous agent loop, run it in your client.
</details>

## 🤝 Contributing

Contributions are welcome! Whether it's fixing bugs, adding new research tools, or improving documentation, your help is appreciated.

1. **Fork the Project**
2. **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your Changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the Branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

## 💡 Issues, Feedback & Support

Found a bug, have a feature request, or want to share how you're using RivalSearchMCP? We'd love to hear from you!

- **Report a bug** — Help us improve by reporting issues
- **Request a feature** — Suggest new capabilities you'd find useful
- **Share your use case** — Tell us how you're using RivalSearchMCP

👉 **[Open an Issue](https://github.com/damionrashford/RivalSearchMCP/issues)**

## 📡 Stay in the Loop

Building something with RivalSearchMCP? Join the clan — every release brings new capabilities for AI-native PMs and engineers.

| Channel | Link |
|---|---|
| 🚀 **Releases** | [GitHub Releases page](https://github.com/damionrashford/RivalSearchMCP/releases) — versioned changelog with what's new |
| 📰 **RSS / Atom feed** | [`releases.atom`](https://github.com/damionrashford/RivalSearchMCP/releases.atom) — pipe into Slack, Discord, your RSS reader, or any feed-to-webhook tool |
| 🗨️ **Discussions** | [GitHub Discussions](https://github.com/damionrashford/RivalSearchMCP/discussions) — show & tell, agent recipes, wishlist, help |
| 👀 **Watch the repo** | [Subscribe to releases](https://github.com/damionrashford/RivalSearchMCP/subscription) — GitHub-native notifications |
| 💼 **Author** | [Damion Rashford on LinkedIn](https://www.linkedin.com/in/damion-rashford) |

## Attribution & License

This is an open source project under the **MIT License**. If you use RivalSearchMCP, please credit it by linking back to [RivalSearchMCP](https://github.com/damionrashford/RivalSearchMCP). See [LICENSE](LICENSE) file for details.

## ⭐ Like this project? Give it a star!

If you find RivalSearchMCP useful, please consider giving it a star. It helps others discover the project and motivates continued development!

[![Star this repo](https://img.shields.io/github/stars/damionrashford/RivalSearchMCP?style=social)](https://github.com/damionrashford/RivalSearchMCP)
