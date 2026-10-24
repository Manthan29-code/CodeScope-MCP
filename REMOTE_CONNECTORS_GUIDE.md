# 🌐 Remote MCP Connectors Guide: Claude, ChatGPT & Gemini

> **Step-by-step setup guide for connecting CodeScope MCP to cloud Chat LLMs via Streamable HTTP & ngrok.**

---

## 🎯 Target Audience: Why CodeScope MCP is Built for Chat LLMs (No Meaning to Use with AI IDEs)

> [!IMPORTANT]
> **CodeScope MCP is made specifically for Cloud Chat LLMs (Claude.ai, ChatGPT, Google Gemini). There is NO meaning or reason to use it with AI IDEs (Antigravity, Cursor, Windsurf).**

| Environment | Local Filesystem Access | Needs CodeScope MCP? | Why? |
| :--- | :--- | :--- | :--- |
| **Cloud Chat LLMs**<br>*(Claude.ai, ChatGPT, Google Gemini)* | ❌ **Zero Access**<br>(Runs in isolated cloud web sandboxes) | ✅ **YES (Sole Purpose)** | Cloud chat applications run on remote cloud servers and are completely incapable of reading, searching, or editing files on your local machine. CodeScope MCP gives them secure, controlled access over ngrok. |
| **AI IDEs**<br>*(Antigravity, Cursor, Windsurf)* | 🟢 **Native Full Access**<br>(Runs on host machine) | ❌ **No (Meaningless)** | AI IDEs already execute directly on your computer with native OS filesystem read/write access, integrated terminals, and editor workspaces. Connecting an external HTTP MCP server in an AI IDE is completely redundant and pointless. |

### The Core Problem CodeScope Solves for Chat LLMs
Web-based chat models like Claude.ai, ChatGPT Web, and Google Gemini Web are exceptionally powerful reasoning engines, but they are completely blind to your local disk and files. Normally, developers are forced to manually copy-paste code snippets into chat prompts, losing project structure and wasting prompt context.

**CodeScope MCP turns your browser chat into a local codebase assistant**:
1. You run CodeScope MCP locally on your project.
2. You expose it securely with an **ngrok tunnel** (`https://<subdomain>.ngrok-free.app/mcp`).
3. You add it as a custom remote connector in Claude, ChatGPT, or Gemini.
4. Your cloud chat LLM can now list directory trees, search code with regex, read specific line ranges, and apply diff patches directly on your local computer—protected by strict allowlists (`READ_ALLOWED_ROOTS` and `WRITE_ALLOWED_ROOTS`).

---

## 📋 Prerequisites & Public Endpoint Generation

Ensure your server is running and tunneled before configuring any chat connector.

### Step 1: Start CodeScope MCP Locally
In your project directory:
```bash
python main.py
```
Expected output:
```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Step 2: Launch ngrok HTTP Tunnel
In a second terminal window:
```bash
ngrok http 8000
```
ngrok will display a public forwarding address:
```text
Forwarding                    https://a1b2-c3d4.ngrok-free.app -> http://localhost:8000
```

### Step 3: Copy Your Public MCP Endpoint
Always append `/mcp` to your ngrok URL:
```text
https://a1b2-c3d4.ngrok-free.app/mcp
```

> [!WARNING]
> **Always append `/mcp`!** Accessing the base URL (`https://a1b2-c3d4.ngrok-free.app/`) will return `404 Not Found`. FastMCP's Streamable HTTP handler listens exclusively at the `/mcp` path.

> [!IMPORTANT]
> ### 🔑 Authentication: Keep "No authentication" in all setups!
> CodeScope MCP runs **without an authentication layer** (it does not require API keys, bearer tokens, or OAuth passwords).
> Host security is enforced through:
> 1. Your private, ephemeral ngrok tunnel URL.
> 2. Strict server-side filesystem boundaries (`ALLOWED_PROJECT_ROOTS`, `READ_ALLOWED_ROOTS`, `WRITE_ALLOWED_ROOTS`).
> 
> **For Claude, ChatGPT, and Google Gemini: ALWAYS choose "No authentication" (or "None")**.
> If you select Bearer Token, OAuth, or Basic Auth, the handshake will fail.

---

## 🤖 1. Connecting to Claude (Anthropic Remote MCP Connectors)

Official documentation: [Anthropic — Remote MCP connectors](https://support.anthropic.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp).  
*Note: Custom remote connectors in Claude are available on eligible paid plans (Claude Pro, Team, and Enterprise).*

```
┌────────────────────────────────────────────────────────┐
│ Claude.ai Settings > Connectors > Add Custom Connector │
│                                                        │
│ Name:           CodeScope MCP                          │
│ URL:            https://a1b2-c3d4.ngrok-free.app/mcp   │
│ Authentication: None / No authentication  ◄── (KEEP!)  │
│                                                        │
│ [ Add Connector ] ────────► Discovers tools            │
└────────────────────────────────────────────────────────┘
```

### Walkthrough:
1. **Open Claude**:
   - Navigate to [claude.ai](https://claude.ai/) and sign in to your paid account.
2. **Open Settings → Connectors**:
   - Click on your profile icon in the lower-left corner and select **Settings**.
   - Navigate to the **Connectors** (or **Integrations**) tab.
   - Click the **Add custom connector** button.
3. **Enter Your MCP Details**:
   - **Connector Name**: `CodeScope MCP`
   - **Remote MCP server URL**: `https://<your-subdomain>.ngrok-free.app/mcp` *(e.g., `https://a1b2-c3d4.ngrok-free.app/mcp`)*
   - **Authentication**: Leave as **None / No authentication** (do not provide auth headers).
   - Click **Add** to validate and save the connector.
4. **Connect and Enable Tools**:
   - Complete any on-screen confirmation checks. Claude will query the `/mcp` endpoint and auto-discover all available CodeScope tools (`list_directory_tree`, `read_file`, `search_files_by_content`, `apply_diff_patch`, etc.).
   - Start a new chat, open the **Search and tools** panel (or attachments/tools toggle), ensure **CodeScope MCP** is enabled, and select the tools you want Claude to utilize.

---

## 💬 2. Connecting to ChatGPT (OpenAI Custom MCP Servers)

Official documentation: [ChatGPT custom MCP server setup](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt).

```
┌────────────────────────────────────────────────────────────┐
│ ChatGPT Settings > Apps > Add Custom MCP Server            │
│                                                            │
│ Connection:     (●) Server URL    ( ) Tunnel               │
│                 https://<your-subdomain>.ngrok-free.app/mcp│
│                                                            │
│ Authentication: No authentication  ◄─── (KEEP AS DEFAULT!) │
│                                                            │
│ ⚠ Custom MCP servers introduce risk.                       │
│ [x] I understand and want to continue                      │
│                                                            │
│ [ Cancel ]                   [ Create as a plugin / Add ]  │
└────────────────────────────────────────────────────────────┘
```

### Walkthrough:
1. **Open ChatGPT Settings**:
   - Open [chatgpt.com](https://chatgpt.com/) in your browser.
   - Go to **Settings** → **Apps** (or your Workspace App Configuration if using an Enterprise account).
2. **Add a Custom MCP Server**:
   - Click **Add custom MCP server** (or **New MCP Connection**).
   - Fill in the connection form:
     - **Name**: `CodeScope MCP` (or enter in description if prompted).
     - **Connection**: Select **Server URL** and enter: `https://<your-subdomain>.ngrok-free.app/mcp` *(e.g. `https://steadier-written-alienable.ngrok-free.dev/mcp`)*
     - **Authentication**: Select **No authentication** *(CodeScope does not use bearer/API tokens)*.
     - **Risk Confirmation**: Check the box **"I understand and want to continue"**.
     - Click **Create as a plugin** (or **Add**).
3. **Test and Enable Tools**:
   - Review the connection and confirm discovered tools. ChatGPT will ping the endpoint and list registered capabilities.
   - **Verification Test**: In your prompt, ask ChatGPT to inspect your project before performing any write operations (e.g., `"Use CodeScope to list the directory tree of this project"`).

---

## 🔮 3. Connecting to Google Gemini (Gemini Web App)

For Google accounts with custom app integration and MCP connector preview enabled at [gemini.google.com](https://gemini.google.com/):

```
┌────────────────────────────────────────────────────────┐
│ gemini.google.com > Settings (⚙️) > Connected Apps     │
│                                                        │
│ Look for:       Add a custom app / MCP Server          │
│ App Name:       CodeScope MCP                          │
│ MCP URL:        https://a1b2-c3d4.ngrok-free.app/mcp   │
│ Authentication: None / No authentication  ◄── (KEEP!)  │
│                                                        │
│ In Chat:        Use @CodeScope to trigger tools        │
└────────────────────────────────────────────────────────┘
```

### Walkthrough:
1. **Open Gemini Web**:
   - Navigate to [gemini.google.com](https://gemini.google.com/) and sign in.
2. **Open Connected Apps**:
   - Click the **Settings (gear icon)** in the sidebar or bottom menu.
   - Select **Connected Apps** (or **Personal Intelligence → Connected Apps**).
3. **Add Custom MCP Server**:
   - Click **Custom apps** or **Add a custom app / MCP Server**.
   - Enter your connection details:
     - **App / Server Name**: `CodeScope` (or `CodeScope MCP`)
     - **MCP Server URL**: `https://<your-subdomain>.ngrok-free.app/mcp` *(e.g., `https://a1b2-c3d4.ngrok-free.app/mcp`)*
     - **Authentication**: Set to **None / No authentication**.
4. **Authorize Connection**:
   - Complete any on-screen authorization checks. Gemini will verify connectivity with your local server.
5. **Triggering CodeScope Tools in Gemini Chat**:
   - In your Gemini chat box, trigger your custom server tools using `@CodeScope` or `@YourAppName`:
     ```text
     @CodeScope list the directory tree of the project and find where database connections are established.
     ```

---

## 💡 Recommended Chat Prompts & Usage Patterns

When interacting with CodeScope MCP from Claude, ChatGPT, or Gemini, follow this phased approach for maximum token efficiency:

### Phase 1: High-Level Exploration
Ask the model to inspect structure without loading full files:
```text
Use CodeScope to list the directory tree for project_path="." with max_depth=2.
```

### Phase 2: Targeted Search
Find relevant code snippets using content search or regex:
```text
Search for the pattern "def get_db" across Python files using search_files_by_content.
```

### Phase 3: Paginated Reading
Read only the lines necessary to understand or debug:
```text
Read lines 1 to 60 of services/database.py using read_file with offset=1 and limit=60.
```

### Phase 4: Precision Editing (If Write Tools Enabled)
Provide structured edits without rewriting entire files:
```text
Use apply_diff_patch or apply_single_edit to update the timeout parameter in config.py.
```

---

## 🛡️ Security Checklists for Remote Chat LLMs

Connecting a remote cloud LLM to your local machine requires strict safeguards. CodeScope MCP enforces these by default:

1. **Path Allowlist Boundary (`ALLOWED_PROJECT_ROOTS`)**:
   - The LLM can **never** access files outside the folders explicitly declared in your `.env` (e.g. `ALLOWED_PROJECT_ROOTS=C:\MyProject` or `/Users/alice/projects`). Attempts to access `C:\Windows` or `/etc` return an immediate security refusal.
2. **Explicit Write Opt-In (`ENABLE_WRITE_TOOLS=false`)**:
   - Keep `ENABLE_WRITE_TOOLS=false` if you only want the chat LLM to explore and read code without modifying files.
3. **Token & Size Caps**:
   - `MAX_LINES_PER_READ` and `MAX_WRITE_SIZE_BYTES` protect both your context budget and local disk integrity against runaway LLM loops.
4. **Terminate Tunnel When Finished**:
   - When your chat session is complete, simply press `Ctrl+C` in your ngrok terminal window to close public exposure immediately.

---

## ❓ Troubleshooting Remote Connections

### `404 Not Found` when adding connector
- **Cause**: The `/mcp` route was omitted from the URL.
- **Solution**: Change `https://xxxx.ngrok-free.app` to `https://xxxx.ngrok-free.app/mcp`.

### Connection Timeout / Network Error
- **Cause**: Either `python main.py` or the `ngrok http 8000` tunnel stopped running.
- **Solution**: Verify both processes are active. Open `https://xxxx.ngrok-free.app/mcp` in your browser—it should respond (POST method required for MCP transport).

### "Custom connector not supported on current plan"
- **Cause**: Some providers (e.g. Anthropic Claude) may require eligible subscriptions or specific rollout access for custom remote connectors.
- **Solution**: Ensure your account has custom connector access enabled in Settings.

---

## 🔗 Related Documentation
- [README.md](file:///c:/MyProject/CodeScope%20MCP/README.md) — Main repository overview, features, and local setup.
- [CONFIGURATION_GUIDE.md](file:///c:/MyProject/CodeScope%20MCP/CONFIGURATION_GUIDE.md) — Comprehensive guide to `.env` variables and security sizing presets.
- [BACKEND_DOCUMENTATION.md](file:///c:/MyProject/CodeScope%20MCP/BACKEND_DOCUMENTATION.md) — Internal architecture, FastMCP mechanics, and tool implementations.
