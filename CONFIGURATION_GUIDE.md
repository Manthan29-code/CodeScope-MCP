# ⚙️ CodeScope MCP Configuration & Sizing Guide

This guide provides an in-depth reference for every configuration variable in **CodeScope MCP**, explaining how each parameter affects system behavior, token consumption, and host security. It includes specific sizing recommendations and ready-to-use presets based on the scale and complexity of your project.

---

## 📑 Table of Contents

- [Configuration Architecture](#configuration-architecture)
- [Project Sizing Framework](#project-sizing-framework)
- [Complete Variable Reference](#complete-variable-reference)
  - [1. Server & Transport Settings](#1-server--transport-settings)
  - [2. Access Control & Root Authorization](#2-access-control--root-authorization)
  - [3. Read & Exploration Limits](#3-read--exploration-limits)
  - [4. Write Operations & Safety Controls](#4-write-operations--safety-controls)
  - [5. Search & Regex Engine Controls](#5-search--regex-engine-controls)
  - [6. Git Integration Controls](#6-git-integration-controls)
  - [7. Automated Verification Controls](#7-automated-verification-controls)
- [Project Sizing Matrix (Quick Comparison)](#project-sizing-matrix-quick-comparison)
- [Ready-to-Use Configuration Presets](#ready-to-use-configuration-presets)
  - [Preset A: Small Projects & Microservices](#preset-a-small-projects--microservices)
  - [Preset B: Medium Full-Stack Applications (Recommended Default)](#preset-b-medium-full-stack-applications-recommended-default)
  - [Preset C: Large Monorepos & Heavy Automated Refactoring](#preset-c-large-monorepos--heavy-automated-refactoring)
  - [Preset D: Read-Only Exploration (Zero-Write Risk)](#preset-d-read-only-exploration-zero-write-risk)
- [Platform Delimiters & Gotchas](#platform-delimiters--gotchas)

---

## Configuration Architecture

CodeScope MCP follows a **fail-closed, defense-in-depth** configuration model loaded via [`config.py`](file:///c:/MyProject/CodeScope%20MCP/config.py) using `python-dotenv`:

1. **Environment Variables**: Read from `.env` in the server root or from host environment variables.
2. **Access Control Hierarchy**: The centralized `ALLOWED_PROJECT_ROOTS` acts as the master boundary. Specific `READ_ALLOWED_ROOTS` or `WRITE_ALLOWED_ROOTS` can override it for granular privilege separation.
3. **Fail-Closed Operations**: If an allowlist is empty or if an agent specifies an unauthorized root directory, requests are strictly refused before touching the host filesystem.
4. **Token Firewalls**: File reading, unified diffs, and directory trees are strictly capped to prevent flooding the AI model's context window.

---

## Project Sizing Framework

When tuning CodeScope MCP, choose values matching your project tier:

| Tier | Characteristics | Typical Structure | File Count |
| :--- | :--- | :--- | :--- |
| **Small** | CLI tools, microservices, standalone Python/Node scripts, single packages | Flat directory, few modules, small source files (< 500 lines) | < 100 files |
| **Medium** | Full-stack web apps, SaaS backends, multi-component APIs, frontend SPAs | Backend + Frontend folders, database migrations, assets, vendor packages | 100 – 1,500 files |
| **Large / Monorepo** | Enterprise repositories, monorepos, massive documentation hubs, data pipelines | Multi-package workspaces (`packages/*`, `apps/*`, `services/*`), large schemas, generated code | 1,500 – 20,000+ files |

---

## Complete Variable Reference

### 1. Server & Transport Settings

#### `HOST`
- **Default:** `127.0.0.1`
- **Type:** String (IP Address)
- **Purpose:** IP interface on which the FastMCP HTTP server listens.
- **Recommended Values:**
  - **All local workflows:** Keep `127.0.0.1` (loopback only).
  - **Docker / Containerized environments:** Use `0.0.0.0` so container ports can be mapped to the host.
- **Security Warning:** Never expose `0.0.0.0` on a public or untrusted network without a reverse proxy (e.g. Nginx/Caddy) with authentication.

#### `PORT`
- **Default:** `8000`
- **Type:** Integer
- **Purpose:** TCP port for the Streamable HTTP transport endpoint (`/mcp`).
- **Recommended Values:** Any available non-privileged port (`8000`, `8080`, `9000`).

#### `DEFAULT_PROJECT_PATH`
- **Default:** `.` (resolves to server working directory)
- **Type:** File path (relative or absolute)
- **Purpose:** Fallback workspace directory used when an MCP client passes `"."`, `""`, or a virtual container path (e.g., `/working_dir/` from remote LLMs) that does not exist on the local host.
- **Recommended Values:**
  - **Single-repo workflow:** Absolute path to your active workspace (e.g., `C:\MyProject\MyApp`).
  - **Multi-project workflow:** `.` (current working directory where the server was launched).

---

### 2. Access Control & Root Authorization

CodeScope MCP enforces strict boundary validation on all read and write tools to stop unauthorized directory escapes and path traversal.

#### `ALLOWED_PROJECT_ROOTS`
- **Default:** *None* (empty list `[]`)
- **Type:** Semicolon-separated paths on Windows (`;`), colon-separated on Unix (`:`), or comma-separated.
- **Purpose:** Centralized master allowlist. Automatically populates both `READ_ALLOWED_ROOTS` and `WRITE_ALLOWED_ROOTS` if they are not explicitly specified.
- **Recommended Values:**
  - **Small Project:** Exact path to the repository, e.g. `C:\Projects\Microservice`.
  - **Medium / Large Monorepo:** Parent workspace folder containing all related projects, e.g. `C:\MyProject;D:\Workspaces`.

#### `READ_ALLOWED_ROOTS`
- **Default:** Inherits from `ALLOWED_PROJECT_ROOTS` (or `[]` if omitted)
- **Type:** Delimited file paths
- **Purpose:** Authorizes read tools ([`read_file`](file:///c:/MyProject/CodeScope%20MCP/tools/read_file_tool.py), [`read_multiple_files`](file:///c:/MyProject/CodeScope%20MCP/tools/read_multiple_files_tool.py), [`search_files`](file:///c:/MyProject/CodeScope%20MCP/tools/search_files_tool.py), [`list_directory_tree`](file:///c:/MyProject/CodeScope%20MCP/tools/list_directory_tool.py), [`get_file_metadata`](file:///c:/MyProject/CodeScope%20MCP/tools/file_metadata_tool.py)).
- **Behavior:** Operates in **fail-closed** mode. If empty, all read tools reject requests. Rejects raw filesystem/drive roots (`C:\`, `/`) and sibling prefix traps (e.g. `C:\MyProject-evil`).
- **Recommended Values:**
  - Set to the list of folders your AI agent is authorized to explore and read code from.

#### `WRITE_ALLOWED_ROOTS`
- **Default:** Inherits from `ALLOWED_PROJECT_ROOTS` (or `[]` if omitted)
- **Type:** Delimited file paths
- **Purpose:** Authorizes write tools ([`write_file`](file:///c:/MyProject/CodeScope%20MCP/tools/write_file_tool.py), [`edit_file`](file:///c:/MyProject/CodeScope%20MCP/tools/edit_file_tool.py), [`delete_file`](file:///c:/MyProject/CodeScope%20MCP/tools/delete_file_tool.py), [`move_file`](file:///c:/MyProject/CodeScope%20MCP/tools/move_file_tool.py), [`copy_file`](file:///c:/MyProject/CodeScope%20MCP/tools/copy_file_tool.py), [`replace_in_files`](file:///c:/MyProject/CodeScope%20MCP/tools/replace_in_files_tool.py)).
- **Behavior:** If empty or if `project_path` is not inside an allowed folder, writes are refused immediately.
- **Recommended Values:**
  - Use equal to or narrower than `READ_ALLOWED_ROOTS` (e.g., allow reading shared libraries, but restrict writing only to the active application folder).

---

### 3. Read & Exploration Limits

#### `MAX_FILE_SIZE_BYTES`
- **Default:** `10485760` (10 MB)
- **Type:** Integer (Bytes)
- **Purpose:** Safety ceiling for reading files and full-text content searching. Files exceeding this threshold are skipped during search and refused during reading to prevent out-of-memory errors and context exhaustion.
- **Recommended Values:**
  - **Small Project:** `2097152` (2 MB) — Standard source files rarely exceed 1 MB.
  - **Medium Project:** `5242880` (5 MB) — Accommodates larger data schemas, mock JSONs, and bundle assets.
  - **Large / Monorepo:** `10485760` (10 MB) — Allows reading large generated API definitions, database dumps, or documentation files.

#### `MAX_LINES_PER_READ`
- **Default:** `1000`
- **Type:** Integer (Lines)
- **Purpose:** Controls pagination on `read_file`. If a file has more lines, only `MAX_LINES_PER_READ` lines are returned along with `truncated=True` and line pointers (`start_line`, `end_line`, `total_lines`).
- **Recommended Values:**
  - **Small Project (Short Context Models):** `500` lines (~2,000 tokens). Forces compact chunked inspections.
  - **Medium Project (Balanced):** `1000` lines (~4,000 tokens). Covers most full classes/modules in one call.
  - **Large Monorepo (Long Context Models):** `2000` – `3000` lines. Suitable for Gemini 1.5 Pro, Claude 3.5 Sonnet, or GPT-4o with 128k+ token windows.

#### `ALLOW_SYMLINKS`
- **Default:** `false`
- **Type:** Boolean (`true` / `false`)
- **Purpose:** Controls whether file tools follow symlinks pointing to target paths.
- **Recommended Values:**
  - **Standard Development:** Keep `false`. Prevents symlinks from linking outside the approved project root.
  - **Complex Monorepos (pnpm / yarn workspaces):** Set `true` **only if** your monorepo uses internal symlinks across packages within the same root directory.

---

### 4. Write Operations & Safety Controls

#### `ENABLE_WRITE_TOOLS`
- **Default:** `false` (opt-in)
- **Type:** Boolean (`true` / `false`)
- **Purpose:** Master switch for write and mutation capabilities. When `false`, FastMCP registers only read tools; write tools are not even exposed over the protocol.
- **Recommended Values:**
  - `false` for read-only codebase analysis, code review bots, or untrusted evaluation.
  - `true` when using pair-programming assistants that write, edit, and refactor code.

#### `MAX_WRITE_SIZE_BYTES`
- **Default:** `1000000` (1 MB)
- **Type:** Integer (Bytes)
- **Purpose:** Maximum allowed payload size for creating or replacing a single file via `write_file`, copying via `copy_file`, or replacing in `replace_in_files`.
- **Recommended Values:**
  - **Small Project:** `500000` (500 KB).
  - **Medium Project:** `1000000` (1 MB). Fits almost all source code, SVG assets, and HTML files.
  - **Large Monorepo:** `3000000` – `5000000` (3 MB – 5 MB). Useful for writing large mock datasets, Swagger specs, or bundle maps.

#### `MAX_EDITS_PER_CALL`
- **Default:** `50`
- **Type:** Integer
- **Purpose:** Maximum number of sequential edit operations allowed in a single [`edit_file`](file:///c:/MyProject/CodeScope%20MCP/tools/edit_file_tool.py) tool call.
- **Recommended Values:**
  - **Small Project:** `20` – Enforces small, granular edits.
  - **Medium Project:** `50` – Allows comprehensive multi-function refactorings in a single turn.
  - **Large Monorepo:** `100` – For mass renaming or multi-part architectural changes across a large module.

#### `MAX_DIFF_CHARS`
- **Default:** `50000` (or `20000`)
- **Type:** Integer (Characters)
- **Purpose:** Truncation cap for the unified diff string generated by `diff_utils.py` and returned to the client upon write/edit operations.
- **Recommended Values:**
  - **Small Context / Token-Budget Conscious:** `10000` – `20000` chars (~2.5k – 5k tokens).
  - **Medium Project (Balanced):** `50000` chars (~12k tokens). Provides full visibility of changes without truncating typical diffs.
  - **Large Refactorings (Long Context Models):** `100000` chars (~25k tokens). Ensures extensive multi-file changes show complete diffs.

#### `BLOCK_WRITES_TO_IGNORED`
- **Default:** `true`
- **Type:** Boolean (`true` / `false`)
- **Purpose:** When `true`, write tools refuse to write, edit, delete, or rename files matched by `.gitignore` or built-in patterns (`node_modules/`, `.git/`, `.venv/`, `dist/`, `package-lock.json`, etc.).
- **Recommended Values:**
  - **Always `true`**: Protects against accidental corruption of dependencies, virtualenvs, or lockfiles.

---

### 5. Search & Regex Engine Controls

#### `MAX_FILES_PER_REPLACE`
- **Default:** `100`
- **Type:** Integer (File count)
- **Purpose:** Safety threshold for project-wide string replacement via [`replace_in_files`](file:///c:/MyProject/CodeScope%20MCP/tools/replace_in_files_tool.py). If a search pattern matches more than this number of files, the entire transaction aborts before touching disk.
- **Recommended Values:**
  - **Small Project:** `25` – Prevents an overly generic regex from modifying the entire repository.
  - **Medium Project:** `100` – Accommodates standard component or import renames.
  - **Large Monorepo:** `250` – `500` – Needed when refactoring shared core libraries imported by dozens of downstream packages.

#### `REGEX_TIMEOUT_SECONDS`
- **Default:** `2.0` (Seconds)
- **Type:** Float
- **Purpose:** Guards against **ReDoS** (Regular Expression Denial of Service). If an LLM submits a pathologically backtracking regex (e.g. `(a+)+$`), the operation terminates after this duration.
- **Recommended Values:**
  - **Small Project:** `1.0` – Catches backtracking almost instantly.
  - **Medium Project:** `2.0` – Sufficient for scanning large directories without false positives.
  - **Large Monorepo:** `3.0` – `5.0` – Allows scanning thousands of files on slower drives or network volumes.

#### `MAX_REGEX_PATTERN_LENGTH`
- **Default:** `500` (Characters)
- **Type:** Integer
- **Purpose:** Caps the length of regex queries submitted to search and replace tools.
- **Recommended Values:**
  - **Small / Medium Project:** `500` – Ample for complex regexes.
  - **Large Monorepo / Machine-Generated Queries:** `1000` – Needed if agents build large alternation patterns (e.g., `(patternA|patternB|...|patternZ)`).

---

### 6. Git Integration Controls

#### `ENABLE_GIT_TOOLS`
- **Default:** `false`
- **Type:** Boolean (`true` / `false`)
- **Purpose:** Enables Git inspection and manipulation tools. When `false`, no Git tools are registered.
- **Tools Enabled:**
  - Read: `git_status`, `git_diff`, `git_log`, `git_show`, `git_branch_list`
  - Write (if `ENABLE_WRITE_TOOLS=true`): `git_branch_create`, `git_switch`, `git_merge`, `git_revert`, `git_restore`, `git_commit`, `git_push`, `confirm_action`

#### `GIT_CONFIRM_MODE`
- **Default:** `auto`
- **Type:** String (`auto` | `elicit` | `code`)
- **Purpose:** Mechanism for authorizing dangerous actions (`git_merge`, `git_revert`, `git_restore`, `git_commit`, `git_push`).
  - `auto`: Attempts client-side UI elicitation (`ctx.elicit()`) if supported; falls back to console approval code.
  - `elicit`: Requires client UI elicitation (fails if unsupported by client).
  - `code`: Prints a 6-digit one-time code to server console (stderr) only. The user reads and provides it to the model.

> [!IMPORTANT]
> **Human-in-the-Loop Git Integrity & Safety:**
> - `git_commit`: Stages approved changes and records a permanent commit under your Git author identity (`user.name`, `user.email`, GPG key). Protected files (`.env`, private keys) are automatically excluded from staging. Requires human approval to prevent intermediate dirty micro-commits during multi-step AI tasks.
> - `git_push`: Publishes commits from the active local branch to a configured remote repository (e.g. GitHub) using safe, non-force push. Requires human authorization to prevent accidental or unauthorized code distribution.

#### `GIT_CONFIRM_TTL_SECONDS`
- **Default:** `300` (5 minutes)
- **Type:** Integer (Seconds)
- **Purpose:** Expiration time for pending approval actions.

#### `GIT_COMMAND_TIMEOUT_SECONDS`
- **Default:** `30`
- **Type:** Integer (Seconds)
- **Purpose:** Subprocess execution timeout for Git commands.

#### `GIT_MAX_DIFF_LINES`
- **Default:** `2000`
- **Type:** Integer
- **Purpose:** Maximum lines returned for `git_diff` and `git_show`.

---

### 7. Automated Verification Controls

#### `ENABLE_VERIFICATION_TOOLS`
- **Default:** `false`
- **Type:** Boolean (`true` / `false`)
- **Purpose:** Enables verification tools (`list_checks`, `run_check`, `run_all_checks`).
- **Security:** Arbitrary shell commands are strictly disallowed. Only predefined checks in `.codescope.toml` or safe auto-detected project commands can run.

#### `VERIFY_CONFIG_FILENAME`
- **Default:** `.codescope.toml`
- **Type:** String
- **Purpose:** Configuration filename in project root defining authorized checks. This file is protected against model modification.

#### `VERIFY_AUTODETECT`
- **Default:** `true`
- **Type:** Boolean (`true` / `false`)
- **Purpose:** When `.codescope.toml` is absent, automatically discovers lint/test/build tasks from `pyproject.toml`, `package.json`, `Cargo.toml`, or `go.mod`.

#### `VERIFY_DEFAULT_TIMEOUT_SECONDS`
- **Default:** `300` (5 minutes)
- **Type:** Integer (Seconds)
- **Purpose:** Timeout per verification check.

#### `VERIFY_MAX_OUTPUT_CHARS`
- **Default:** `20000`
- **Type:** Integer (Characters)
- **Purpose:** Maximum stdout/stderr characters retained per check stream (preserves head and tail).

---

## Project Sizing Matrix (Quick Comparison)

| Variable | Small Project (<100 files) | Medium Project (100–1,500 files) | Large / Monorepo (1,500+ files) | High-Security / Low-RAM |
| :--- | :--- | :--- | :--- | :--- |
| `MAX_FILE_SIZE_BYTES` | `2097152` (2 MB) | `5242880` (5 MB) | `10485760` (10 MB) | `1048576` (1 MB) |
| `MAX_LINES_PER_READ` | `500` | `1000` | `2000` | `300` |
| `ALLOW_SYMLINKS` | `false` | `false` | `true` (if pnpm/yarn) | `false` |
| `MAX_WRITE_SIZE_BYTES`| `500000` (500 KB) | `1000000` (1 MB) | `3000000` (3 MB) | `250000` (250 KB) |
| `MAX_EDITS_PER_CALL` | `20` | `50` | `100` | `10` |
| `MAX_DIFF_CHARS` | `20000` | `50000` | `100000` | `10000` |
| `BLOCK_WRITES_TO_IGNORED`| `true` | `true` | `true` | `true` |
| `MAX_FILES_PER_REPLACE` | `25` | `100` | `300` | `10` |
| `REGEX_TIMEOUT_SECONDS` | `1.0` | `2.0` | `3.0` | `0.5` |
| `MAX_REGEX_PATTERN_LENGTH`| `300` | `500` | `1000` | `200` |

---

## Ready-to-Use Configuration Presets

### Preset A: Small Projects & Microservices
*Best for: Standalone CLI apps, Python utilities, microservices, small API services.*

```dotenv
# Server Settings
HOST=127.0.0.1
PORT=8000
DEFAULT_PROJECT_PATH=.
MAX_FILE_SIZE_BYTES=2097152
MAX_LINES_PER_READ=500
ALLOW_SYMLINKS=false

# Access Control
ALLOWED_PROJECT_ROOTS=C:\MyProject\MyService

# Write Operations
ENABLE_WRITE_TOOLS=true
MAX_WRITE_SIZE_BYTES=500000
MAX_EDITS_PER_CALL=25
MAX_DIFF_CHARS=25000
BLOCK_WRITES_TO_IGNORED=true

# Search & Regex
MAX_FILES_PER_REPLACE=25
REGEX_TIMEOUT_SECONDS=1.0
MAX_REGEX_PATTERN_LENGTH=300
```

---

### Preset B: Medium Full-Stack Applications (Recommended Default)
*Best for: Full-stack web applications (FastAPI + React/Vue, Django, Next.js, Node.js), typical team codebases.*

```dotenv
# Server Settings
HOST=127.0.0.1
PORT=8000
DEFAULT_PROJECT_PATH=.
MAX_FILE_SIZE_BYTES=10485760
MAX_LINES_PER_READ=1000
ALLOW_SYMLINKS=false

# Access Control
ALLOWED_PROJECT_ROOTS=C:\MyProject\FullStackApp

# Write Operations
ENABLE_WRITE_TOOLS=true
MAX_WRITE_SIZE_BYTES=1000000
MAX_EDITS_PER_CALL=50
MAX_DIFF_CHARS=50000
BLOCK_WRITES_TO_IGNORED=true

# Search & Regex
MAX_FILES_PER_REPLACE=100
REGEX_TIMEOUT_SECONDS=2.0
MAX_REGEX_PATTERN_LENGTH=500
```

---

### Preset C: Large Monorepos & Heavy Automated Refactoring
*Best for: Multi-package workspaces (`lerna`, `nx`, `turborepo`, `cargo workspaces`), enterprise repositories.*

```dotenv
# Server Settings
HOST=127.0.0.1
PORT=8000
DEFAULT_PROJECT_PATH=.
MAX_FILE_SIZE_BYTES=15728640
MAX_LINES_PER_READ=2500
ALLOW_SYMLINKS=true

# Access Control (Supports multiple root directories)
ALLOWED_PROJECT_ROOTS=C:\MyProject\Monorepo;D:\SharedLibraries

# Write Operations
ENABLE_WRITE_TOOLS=true
MAX_WRITE_SIZE_BYTES=5000000
MAX_EDITS_PER_CALL=100
MAX_DIFF_CHARS=100000
BLOCK_WRITES_TO_IGNORED=true

# Search & Regex
MAX_FILES_PER_REPLACE=300
REGEX_TIMEOUT_SECONDS=4.0
MAX_REGEX_PATTERN_LENGTH=1000
```

---

### Preset D: Read-Only Exploration (Zero-Write Risk)
*Best for: Code review agents, security auditing, safe exploration of production source code.*

```dotenv
# Server Settings
HOST=127.0.0.1
PORT=8000
DEFAULT_PROJECT_PATH=.
MAX_FILE_SIZE_BYTES=10485760
MAX_LINES_PER_READ=1000
ALLOW_SYMLINKS=false

# Access Control
READ_ALLOWED_ROOTS=C:\MyProject\AuditTarget

# Write Operations Completely Disabled
ENABLE_WRITE_TOOLS=false
WRITE_ALLOWED_ROOTS=

# Search & Regex
REGEX_TIMEOUT_SECONDS=2.0
MAX_REGEX_PATTERN_LENGTH=500
```

---

## Platform Delimiters & Gotchas

1. **Path Delimiters across Operating Systems**:
   - **Windows**: Use semicolons `;` (e.g. `ALLOWED_PROJECT_ROOTS=C:\ProjectA;D:\ProjectB`). Do not use colons `:` on Windows, as they conflict with drive letters (`C:`).
   - **Linux / macOS**: Use colons `:` (e.g. `ALLOWED_PROJECT_ROOTS=/home/user/projA:/opt/projB`).
   - CodeScope MCP also supports comma-separated paths (`,`) on all operating systems.

2. **Windows Case-Insensitivity**:
   - On Windows, path matching is case-insensitive. `C:\MyProject` matches `c:\myproject` safely.

3. **Protected Paths cannot be overridden**:
   - Regardless of `.env` settings, protected path patterns (`.git/`, `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`) are hardcoded in [`config.py`](file:///c:/MyProject/CodeScope%20MCP/config.py#L70-L80) and can **never** be written to or modified by AI tools.

---

## 🔗 Related Documentation
- [README.md](file:///c:/MyProject/CodeScope%20MCP/README.md) — Main repository overview, features, and quickstart.
- [REMOTE_CONNECTORS_GUIDE.md](file:///c:/MyProject/CodeScope%20MCP/REMOTE_CONNECTORS_GUIDE.md) — Step-by-step connection guide for Claude.ai, ChatGPT, and Google Gemini via ngrok.
- [BACKEND_DOCUMENTATION.md](file:///c:/MyProject/CodeScope%20MCP/BACKEND_DOCUMENTATION.md) — Deep dive into internal architecture and tools.
