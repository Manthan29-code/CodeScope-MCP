from fastmcp import FastMCP
from fastmcp.tools.base import Tool
import config
from utils.logger import logger

from tools import (
    list_directory_tool,
    file_metadata_tool,
    read_file_tool,
    read_multiple_files_tool,
    search_files_tool,
    write_file_tool,
    edit_file_tool,
    delete_file_tool,
    move_file_tool,
    copy_file_tool,
    replace_in_files_tool,
)

SERVER_INSTRUCTIONS = """
CodeScope MCP Server Guidelines:
- Available Git Tools:
  * git_branch_create(name, start_point=None, checkout=False, project_path): Create a new Git branch.
  * git_switch(branch, project_path): Switch to an existing local branch.
  * git_status(project_path): View repository status, staged/unstaged changes, and untracked files.
  * git_diff(path=None, staged=False, base=None, max_lines=500, project_path): View unified diff.
  * git_log(limit=20, path=None, rev=None, project_path): View recent commits.
  * git_show(rev='HEAD', max_lines=500, project_path): View specific commit details and patch.
  * git_branch_list(project_path): List local Git branches.
  * git_merge, git_revert, git_restore, git_commit, git_push: Gated destructive Git actions requiring human approval code.
  * git_commit(message, paths=None, project_path): Stage changes and create a permanent git commit with human approval code.
  * git_push(remote='origin', branch=None, set_upstream=False, project_path): Push local branch commits to remote repository (e.g. GitHub) with human approval code.
  * confirm_action(action_id, approval_code): Execute a previewed dangerous action with the 6-digit code.
- Available Verification Tools:
  * list_checks, run_check, run_all_checks: Run configured or auto-detected test/lint/build checks.
- Project Path: When working on a specific project or sandbox directory (e.g., 'C:\\MyProject\\codescope-sandbox'), always pass that directory path as the project_path argument to read tools, write tools, git tools, and verification tools.
- File Paths: All file paths must be relative to project_path (e.g., 'src/App.jsx', 'css/style.css', 'index.html').
- Code Formatting & Indentation: When writing or editing code files (HTML, CSS, JavaScript, TypeScript, React/JSX/TSX, Python, Java, C/C++, Go, Rust, JSON, YAML, etc.), ALWAYS output clean, beautifully formatted, multi-line source code with standard indentation (2 spaces for HTML/CSS/JS/TS/React/JSON/YAML, 4 spaces for Python/Java/C/C++).
- No Minification: NEVER compress or collapse entire files, functions, HTML tags, or CSS rules into a single line unless specifically requested (e.g. a .min.js or .min.css file).
- Directory Creation: Always set create_parents=True when writing files located in subdirectories so parent folders are automatically created.
"""

# Create FastMCP server instance
mcp = FastMCP("CodeScope", instructions=SERVER_INSTRUCTIONS)

# Register Read Tools (with MCP security annotations)
mcp.add_tool(Tool.from_function(list_directory_tool.list_directory_tree, annotations=list_directory_tool.annotations))
mcp.add_tool(Tool.from_function(file_metadata_tool.get_file_metadata, annotations=file_metadata_tool.annotations))
mcp.add_tool(Tool.from_function(read_file_tool.read_file, annotations=read_file_tool.annotations))
mcp.add_tool(Tool.from_function(read_multiple_files_tool.read_multiple_files, annotations=read_multiple_files_tool.annotations))
mcp.add_tool(Tool.from_function(search_files_tool.search_files, annotations=search_files_tool.annotations))

if not config.READ_ALLOWED_ROOTS:
    logger.warning(
        "READ_ALLOWED_ROOTS is empty. All read operations will be refused until allowed roots are configured."
    )
else:
    logger.info(
        f"Read tools initialized with allowed roots: {config.READ_ALLOWED_ROOTS}"
    )

# Register Write Tools (always registered with annotations; guarded at runtime by write_guard.begin_write)
mcp.add_tool(Tool.from_function(write_file_tool.write_file, annotations=write_file_tool.annotations))
mcp.add_tool(Tool.from_function(edit_file_tool.edit_file, annotations=edit_file_tool.annotations))
mcp.add_tool(Tool.from_function(delete_file_tool.delete_file, annotations=delete_file_tool.annotations))
mcp.add_tool(Tool.from_function(move_file_tool.move_file, annotations=move_file_tool.annotations))
mcp.add_tool(Tool.from_function(copy_file_tool.copy_file, annotations=copy_file_tool.annotations))
mcp.add_tool(Tool.from_function(replace_in_files_tool.replace_in_files, annotations=replace_in_files_tool.annotations))

if not config.WRITE_ALLOWED_ROOTS:
    logger.warning(
        "Write tools registered, but WRITE_ALLOWED_ROOTS is empty. "
        "All write operations will be refused until allowed roots are configured."
    )
else:
    logger.info(
        f"Write tools registered with allowed roots: {config.WRITE_ALLOWED_ROOTS}"
    )

# Register Git Integration Tools (always registered; guarded at runtime by _get_git_service)
from services.confirmation_service import ApprovalGate, ConfirmationService
from services.git_service import GitService
from tools.git_tools import register_git_tools

git_service = GitService(
    config.PROJECT_ROOT,
    timeout=config.GIT_COMMAND_TIMEOUT_SECONDS,
    max_diff_lines=config.GIT_MAX_DIFF_LINES,
    block_ignored=config.BLOCK_WRITES_TO_IGNORED,
)
gate = ApprovalGate(ConfirmationService(config.GIT_CONFIRM_TTL_SECONDS))
register_git_tools(mcp, git_service, gate, enable_write_tools=True)
logger.info("Registered Git tools (guarded at runtime by ENABLE_GIT_TOOLS).")

# Register Automated Verification Tools (always registered; guarded at runtime by _get_verification_service)
from services.verification_service import VerificationService
from tools.verify_tools import register_verify_tools

verifier = VerificationService(
    config.PROJECT_ROOT,
    config_filename=config.VERIFY_CONFIG_FILENAME,
    autodetect=config.VERIFY_AUTODETECT,
    default_timeout=config.VERIFY_DEFAULT_TIMEOUT_SECONDS,
    max_output_chars=config.VERIFY_MAX_OUTPUT_CHARS,
)
register_verify_tools(mcp, verifier)
logger.info("Registered Automated Verification tools: list_checks, run_check, run_all_checks.")

