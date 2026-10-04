# 🔭 CodeScope MCP

> **Intelligent, Token-Optimized Codebase Context MCP Server for AI Agents & LLMs.**

CodeScope MCP provides LLMs and AI assistants with controlled, intelligent, and context-efficient access to local codebases over the **Model Context Protocol (MCP)** using **Streamable HTTP transport**.

Instead of naively dumping entire folders or overwhelming context windows with garbage files (`node_modules`, `.venv`, binaries, lock files), CodeScope acts as a security and context firewall, offering a layered toolset for codebase exploration, code search, and file retrieval.

---

## 📑 Table of Contents

- [What This Is About](#-what-this-is-about)
- [Why You Should Use It](#-why-you-should-use-it)
- [What It Does (Core Tools)](#-what-it-does-core-tools)
- [Architecture Overview](#-architecture-overview)
- [System Flow & Layered Discovery](#-system-flow--layered-discovery)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation & Setup](#installation--setup)
  - [Environment Configuration](#environment-configuration)
  - [Running the Server](#running-the-server)
- [Exposing with ngrok (Remote / Cloud Setup)](#-exposing-with-ngrok-remote--cloud-setup)
- [Connecting to MCP Clients](#-connecting-to-mcp-clients)
- [Security & Constraints](#-security--constraints)
- [Running Tests](#-running-tests)
- [License](#-license)

---

## 💡 What This Is About

When using AI coding assistants or LLM chat agents over MCP, granting raw filesystem access often leads to:
1. **Context Window Blowup**: Giant folders like `node_modules/`, `.git/`, `dist/`, or `.venv/` flooding prompt tokens.
2. **High Token Costs & Slow Responses**: Reading multi-megabyte files or large lock files (`package-lock.json`, `poetry.lock`).
3. **Binary Corruption**: Unintended dumping of binary or compiled files (`.pyc`, images, `.exe`, `.so`) into text prompts.
4. **Security Vulnerabilities**: Path traversal attacks (e.g. `../../../../etc/passwd` or accessing sensitive files outside project roots).

**CodeScope MCP** bridges this gap. It provides a standardized MCP server built on **FastMCP** with **Streamable HTTP** that delivers smart, token-efficient, `.gitignore`-aware file reading, fast code/regex search, and metadata analysis.

---

## 🚀 Why You Should Use It

| Feature / Problem | Raw Filesystem Tools | CodeScope MCP |
| :--- | :--- | :--- |
| **Context Consumption** | Dumps thousands of irrelevant files | `.gitignore` aware + built-in fallback ignore lists |
| **File Reading Strategy** | Reads whole files blindly | Line-by-line pagination (`offset`/`limit`) & batch reads |
| **Search Capabilities** | Slow or nonexistent grep | High-speed content & filename search with pagination |
| **Binary File Protection** | Crashes or spits corrupted ASCII | Automatic binary detection & safe refusal |
| **Security Containment** | Risks root escaping | Strict path resolution & traversal protection |
| **Token Estimation** | None | Real-time token estimates before reading |
| **Modern Transport** | Stdio or legacy SSE | **Streamable HTTP** (FastMCP 2.x standard) |

---

## 🛠️ What It Does (Core Tools)

CodeScope registers 5 specialized tools designed for progressive discovery (from cheapest context cost to full retrieval):

### 1. `list_directory_tree`
Generates a hierarchical directory tree starting from the project root.
- **Ignore Filtering**: Filters out `.git`, `node_modules`, `.venv`, `.next`, cache files, and custom `.gitignore` patterns.
- **Controls**: Supports `max_depth` limits and toggling hidden files (`include_hidden`).
- **Token Hints**: Supplies file sizes and token estimates per file directly inside the tree nodes.

### 2. `search_files`
Performs fast grep-like search across files or searches matching filenames.
- **Search Modes**: `content` (grep search within file contents) or `filename` (find files by name).
- **Filters & Regex**: Supports regex queries, glob file patterns (e.g., `*.py`, `src/**/*.ts`), and case sensitivity.
- **Pagination**: Includes `offset` and `max_results` (with `has_more` flag) to prevent prompt overflows.

### 3. `get_file_metadata`
Inspects file properties without consuming context on the file body.
- Returns file size in bytes, ISO 8601 last modified timestamp, detected programming language/format, binary status, and rough token estimate.

### 4. `read_file`
Safely reads text file contents with built-in safeguards.
- **Pagination**: Supports 0-indexed line `offset` and `limit` to read chunks of large files.
- **Safety**: Automatically rejects binary files and enforces maximum file size and line caps.

### 5. `read_multiple_files`
Batch file retrieval utility to fetch multiple files in a single MCP tool call.
- Reduces network round-trips and conversational turns when pulling code references found via search.

---

## 🏗️ Architecture Overview

The following Mermaid diagram illustrates the internal components and request flow of CodeScope MCP:

```mermaid
graph TD
    subgraph ClientLayer ["1. Client & Network Layer"]
        Client["AI Assistant / LLM Agent<br/>(Claude Desktop, Cursor, Custom Agent)"]
        Tunnel["ngrok Secure Tunnel<br/>(Public HTTPS URL)"]
        Client -->|Streamable HTTP / JSON-RPC| Tunnel
        Tunnel -->|Forward to Local Port 8000| Server["FastMCP Server<br/>(Streamable HTTP Transport)"]
    end

    subgraph ToolsLayer ["2. MCP Tools Interface"]
        Server --> T1["list_directory_tree"]
        Server --> T2["search_files"]
        Server --> T3["get_file_metadata"]
        Server --> T4["read_file"]
        Server --> T5["read_multiple_files"]
    end

    subgraph ServicesLayer ["3. Services Layer"]
        T1 --> TreeSvc["TreeService<br/>(tree_service.py)"]
        T2 --> SearchSvc["SearchService<br/>(search_service.py)"]
        T3 --> MetaSvc["MetadataService<br/>(metadata_service.py)"]
        T4 --> ReadSvc["ReadService<br/>(read_service.py)"]
        T5 --> ReadSvc
    end

    subgraph CoreLayer ["4. Core Security & Analysis"]
        TreeSvc & SearchSvc & ReadSvc & MetaSvc --> PathSec["PathSecurity<br/>(Containment & Symlink checks)"]
        TreeSvc & SearchSvc --> IgnoreMgr["IgnoreManager<br/>(pathspec + Default Fallbacks)"]
        ReadSvc & MetaSvc --> Classifier["FileClassifier<br/>(Binary check + Language map)"]
        ReadSvc & MetaSvc & TreeSvc --> TokenEst["TokenEstimator<br/>(Token count calculation)"]
    end

    subgraph StorageLayer ["5. Local Storage"]
        PathSec & ReadSvc & SearchSvc --> LocalFS["Local Project Filesystem"]
    end

    classDef client fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff;
    classDef tools fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff;
    classDef services fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff;
    classDef core fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:#fff;
    classDef storage fill:#64748b,stroke:#334155,stroke-width:2px,color:#fff;

    class Client,Tunnel,Server client;
    class T1,T2,T3,T4,T5 tools;
    class TreeSvc,SearchSvc,MetaSvc,ReadSvc services;
    class PathSec,IgnoreMgr,Classifier,TokenEst core;
    class LocalFS storage;
```

---

## 🔄 System Flow & Layered Discovery

To optimize context usage, LLMs interact with CodeScope using a progressive **cheap $\rightarrow$ expensive** workflow:

```mermaid
sequenceDiagram
    autonumber
    actor LLM as LLM Agent
    participant MCP as CodeScope MCP
    participant Core as Core Engine
    participant FS as Local Filesystem

    Note over LLM,FS: Phase 1: Exploration
    LLM->>MCP: list_directory_tree(project_path, max_depth=2)
    MCP->>Core: Apply .gitignore & fallback filters
    Core->>FS: Scan directory structure
    FS-->>MCP: Directory items
    MCP-->>LLM: Filtered tree with token estimates

    Note over LLM,FS: Phase 2: Targeted Search
    LLM->>MCP: search_files(query="def authenticate", search_type="content")
    MCP->>Core: Grep matching files (skipping ignored)
    Core->>FS: Scan files
    FS-->>MCP: Matches with line numbers & snippets
    MCP-->>LLM: Paginated search results

    Note over LLM,FS: Phase 3: Metadata / Inspection
    LLM->>MCP: get_file_metadata(file_path="services/auth.py")
    MCP->>Core: Inspect size, language & tokens
    MCP-->>LLM: { size: 1420 bytes, tokens: ~350, is_binary: false }

    Note over LLM,FS: Phase 4: Targeted / Paginated Read
    LLM->>MCP: read_file(file_path="services/auth.py", offset=0, limit=100)
    MCP->>Core: Validate path security & binary status
    Core->>FS: Read requested line slice
    FS-->>MCP: Content slice
    MCP-->>LLM: Formatted file content with line numbers
```

---

## 📁 Project Structure

```
CodeScope MCP/
├── main.py                     # Server entrypoint (loads .env and starts FastMCP)
├── server.py                   # FastMCP instance & tool registrations
├── config.py                   # Configuration settings, defaults & ignore patterns
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment variables
│
├── core/                       # Core security, classification & parsing logic
│   ├── path_security.py        # Path resolution, root containment & symlink policy
│   ├── ignore_manager.py       # .gitignore parsing (pathspec) & fallback ignores
│   ├── file_classifier.py      # Binary vs text detection & language mapping
│   └── token_estimator.py      # Token & character count estimation helper
│
├── services/                   # Business logic for MCP operations
│   ├── tree_service.py         # Builds filtered directory hierarchy
│   ├── search_service.py       # Regex & string search (content & filename)
│   ├── read_service.py         # Single & batch file reading with pagination
│   └── metadata_service.py     # File statistics & token inspection
│
├── tools/                      # MCP Tool wrapper endpoints
│   ├── list_directory_tool.py  # list_directory_tree tool
│   ├── search_files_tool.py    # search_files tool
│   ├── file_metadata_tool.py   # get_file_metadata tool
│   ├── read_file_tool.py       # read_file tool
│   └── read_multiple_files_tool.py # read_multiple_files batch tool
│
├── models/                     # Pydantic data schemas & contracts
│   └── schemas.py              # Input / output request & response models
│
├── utils/                      # Utilities & logging
│   └── logger.py               # Configured standard logger
│
└── tests/                      # Pytest unit & integration test suite
    ├── test_path_security.py
    ├── test_ignore_manager.py
    ├── test_tree_service.py
    ├── test_search_service.py
    └── test_read_service.py
```

---

## ⚡ Getting Started

### Prerequisites

- **Python 3.10+** installed
- **Git** installed

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Manthan29-code/CodeScope-MCP.git
   cd "CodeScope MCP"
   ```

2. **Create and activate a virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Environment Configuration

Create a `.env` file from the example template:

```bash
cp .env.example .env
```

Edit `.env` to configure your settings:

```dotenv
HOST=127.0.0.1
PORT=8000
MAX_FILE_SIZE_BYTES=10485760   # 10 MB limit
MAX_LINES_PER_READ=1000        # Max lines returned per read call
ALLOW_SYMLINKS=false           # Prevent symlink escapes
```

### Running the Server

Start the local server:

```bash
python main.py
```

By default, the server runs on `http://127.0.0.1:8000` with the MCP endpoint accessible at:
```
http://127.0.0.1:8000/mcp
```

---

## 🌐 Exposing with ngrok (Remote / Cloud Setup)

If you are running CodeScope MCP on your local machine and want to connect it to an external AI service, cloud agent, or remote LLM chat platform, you can expose the local Streamable HTTP server via **ngrok**.

### Step 1: Install & Authenticate ngrok

1. Download ngrok from [ngrok.com](https://ngrok.com/download) or install via package manager:
   - **Windows (Winget / Chocolatey):**
     ```powershell
     winget install ngrok.ngrok
     # or
     choco install ngrok
     ```
   - **macOS (Homebrew):**
     ```bash
     brew install ngrok/ngrok/ngrok
     ```
   - **Linux:**
     ```bash
     snap install ngrok
     ```

2. Add your ngrok authtoken (sign up for free at [dashboard.ngrok.com](https://dashboard.ngrok.com)):
   ```bash
   ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
   ```

### Step 2: Start CodeScope MCP Server

Make sure your CodeScope MCP server is running in a terminal:
```bash
python main.py
```
*(Server starts listening on `http://127.0.0.1:8000`)*

### Step 3: Launch ngrok Tunnel

In a separate terminal, start an HTTP tunnel pointing to port `8000`:
```bash
ngrok http 8000
```

ngrok will output a session dashboard similar to:
```text
Session Status                online
Account                       Your Name (Plan: Free)
Forwarding                    https://a1b2-c3d4.ngrok-free.app -> http://localhost:8000
```

### Step 4: Access Your Public MCP Endpoint

Your public MCP URL will be:
```
https://<your-ngrok-subdomain>.ngrok-free.app/mcp
```

*(For example: `https://a1b2-c3d4.ngrok-free.app/mcp`)*

> [!TIP]
> If you have a paid or static ngrok domain, you can keep the URL permanent with:
> `ngrok http --url=your-domain.ngrok-free.app 8000`

---

## 🔌 Connecting to MCP Clients

### Example: MCP Client Configuration (Streamable HTTP)

Add CodeScope to your MCP client configuration (such as Cursor, Claude Desktop, or custom MCP clients):

#### Local Setup:
```json
{
  "mcpServers": {
    "codescope": {
      "url": "http://127.0.0.1:8000/mcp",
      "transport": "streamable-http"
    }
  }
}
```

#### Remote Setup (via ngrok):
```json
{
  "mcpServers": {
    "codescope": {
      "url": "https://a1b2-c3d4.ngrok-free.app/mcp",
      "transport": "streamable-http"
    }
  }
}
```

---

## 🔒 Security & Constraints

- **Strict Path Containment**: Resolves all relative paths against the provided `project_path`. Attempts to escape the directory via `../` or absolute path jumps raise a `SecurityException`.
- **Symlink Refusal**: Rejects symlinks by default (`ALLOW_SYMLINKS=false`) to prevent filesystem traversal via aliased paths.
- **Binary Content Guard**: Uses character inspection and extension mapping to block binary payloads from consuming prompt tokens.
- **File Size & Line Limits**: Enforces hard caps on single read operations to protect against Denial of Service (DoS) and context overflow.

---

## 🧪 Running Tests

CodeScope includes a full pytest suite covering security checks, ignore management, tree construction, search, and reading services.

Run the test suite:
```bash
pytest -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
