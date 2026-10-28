# 🩺 Troubleshooting: "Error in message stream"

If you encounter an **"Error in message stream"** error while using CodeScope MCP with cloud Chat LLMs (Claude.ai, ChatGPT, Google Gemini), especially when asking an AI assistant to make changes across multiple files or read large directories, this guide covers the underlying causes, prevention strategies, and diagnostic steps.

> [!NOTE]
> The MCP server terminal may continue running normally and show `200 OK` or `202 Accepted` even when the AI client fails to receive or parse a complete message stream.

---

## 🔍 Why Can This Happen?

Possible causes include:

- **Large Operations**: Requesting extensive changes across many files in a single prompt can result in oversized tool outputs, long payloads, or excessive consecutive tool calls.
- **Response Size Overflow**: Reading entire files or generating large Git diffs can produce responses that exceed client-side buffer limits or streaming chunk sizes.
- **Environment Limits Reached**: Configured safety thresholds such as `MAX_WRITE_SIZE_BYTES`, `MAX_EDITS_PER_CALL`, and `MAX_DIFF_CHARS` will reject operations when their limits are exceeded, which some clients interpret as stream interruptions.
- **Timeouts or Connection Interruptions**: Long-running operations, client disconnections, or interruptions in the HTTP streaming connection (especially over reverse proxies or tunnels like ngrok) can sever the stream before delivery completes.
- **Unhandled Tool Errors**: Exceptions during file operations, JSON-RPC response serialization, or tool execution that terminate the stream unexpectedly.
- **Concurrent Requests**: Multiple simultaneous requests from the same client session overlapping file operations or competing for process execution locks.

> [!IMPORTANT]
> These are potential root causes, not a single definitive diagnosis. The actual cause should be identified from your server console logs and diagnostic output.

---

## 🛡️ Recommended Approach

To reduce the likelihood of encountering stream errors when working on large features or codebases:

1. **Divide the task into smaller phases**: Ask the AI to inspect the existing implementation, prepare a plan, and implement one logical group of changes at a time.
2. **Prefer targeted edits**: Modify only the relevant sections of existing files using `edit_file` instead of rewriting entire files with `write_file`.
3. **Read selectively**: Use pagination (`offset` and `limit` in `read_file`) rather than requesting entire multi-thousand-line files.
4. **Keep individual operations within configured limits**: Follow the safety limits defined in `.env`. Do not arbitrarily raise limits without understanding why an operation is failing.
5. **Review changes incrementally**: Inspect the Git diff (`git_diff`) and status (`git_status`) between implementation phases.
6. **Investigate the stream itself**: If the error persists, examine the `/mcp` endpoint logs, exception handlers in `utils/error_handler.py`, ngrok web inspection (`http://127.0.0.1:4040`), and proxy timeouts.

---

## 🛠️ Step-by-Step Diagnostic Checklist

| Step | What to Check | Action |
| :--- | :--- | :--- |
| **1. Server Console** | Inspect the terminal running `python main.py` | Look for `[WARNING]` or `[ERROR]` logs. Check if a tool was rejected or raised an unhandled exception. |
| **2. ngrok Web Inspector** | Open `http://127.0.0.1:4040` in your browser | Inspect the exact HTTP request/response payloads, status codes, and payload sizes sent over the tunnel. |
| **3. Chunk / Payload Size** | Response length in characters | If diff or file reads exceed ~100KB, use pagination or restrict the file path. |
| **4. Tunnel Stability** | ngrok session health | Verify ngrok has not expired or reconnected with a new public URL. |

---

## 🤖 How to Investigate the Error Using an AI IDE

If the problem persists, you can paste the diagnostic prompt below into an AI IDE (such as Antigravity or Cursor). Ask it to inspect your local server logs and source code to identify evidence before modifying any settings:

```markdown
I am encountering an "Error in message stream" issue when using CodeScope MCP with my remote chat client.

Please inspect:
1. The recent server logs and console output in `utils/logger.py` and `utils/error_handler.py`.
2. The endpoint configuration in `server.py` and `main.py`.
3. Relevant limits in `config.py` and `.env` (`MAX_DIFF_CHARS`, `MAX_WRITE_SIZE_BYTES`, `GIT_MAX_DIFF_LINES`).

Identify the likely cause with evidence from the codebase and logs, and recommend specific fixes before modifying any files. Do not disable security boundaries or simply raise limits to suppress the error.
```

---

## 🔗 Related Documentation

- [**README.md**](README.md) — Core architecture, security rules, and available tools.
- [**REMOTE_CONNECTORS_GUIDE.md**](REMOTE_CONNECTORS_GUIDE.md) — Setting up Claude, ChatGPT, and Gemini over ngrok.
- [**CONFIGURATION_GUIDE.md**](CONFIGURATION_GUIDE.md) — Comprehensive guide to sizing `.env` limits for small, medium, and large repositories.
