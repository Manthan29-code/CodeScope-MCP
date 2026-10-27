from fastmcp import FastMCP
import config
from utils.logger import logger
from tools.list_directory_tool import list_directory_tree
from tools.file_metadata_tool import get_file_metadata
from tools.read_file_tool import read_file
from tools.read_multiple_files_tool import read_multiple_files
from tools.search_files_tool import search_files

SERVER_INSTRUCTIONS = """
CodeScope MCP Server Guidelines:
- Code Formatting & Indentation: When writing or editing code files (HTML, CSS, JavaScript, TypeScript, React/JSX/TSX, Python, Java, C/C++, Go, Rust, JSON, YAML, etc.), ALWAYS output clean, beautifully formatted, multi-line source code with standard indentation (2 spaces for HTML/CSS/JS/TS/React/JSON/YAML, 4 spaces for Python/Java/C/C++).
- No Minification: NEVER compress or collapse entire files, functions, HTML tags, or CSS rules into a single line unless specifically requested (e.g. a .min.js or .min.css file).
- File Paths: All file paths must be relative to project_path (e.g., 'src/App.jsx', 'css/style.css', 'index.html').
- Project Path: When working on a specific project or sandbox directory (e.g., 'C:\\MyProject\\codescope-sandbox'), always pass that directory path as the project_path argument to read tools, write tools, git tools, and verification tools.
- Directory Creation: Always set create_parents=True when writing files located in subdirectories so parent folders are automatically created.
"""

# Create FastMCP server instance
mcp = FastMCP("CodeScope", instructions=SERVER_INSTRUCTIONS)

# Register Read Tools (always available)
mcp.add_tool(list_directory_tree)
mcp.add_tool(get_file_metadata)
mcp.add_tool(read_file)
mcp.add_tool(read_multiple_files)
mcp.add_tool(search_files)

if not config.READ_ALLOWED_ROOTS:
    logger.warning(
        "READ_ALLOWED_ROOTS is empty. All read operations will be refused until allowed roots are configured."
    )
else:
    logger.info(
        f"Read tools initialized with allowed roots: {config.READ_ALLOWED_ROOTS}"
    )

# Conditionally Register Write Tools (Parts 3 & 4)
if config.ENABLE_WRITE_TOOLS:
    from tools.write_file_tool import write_file
    from tools.edit_file_tool import edit_file
    from tools.delete_file_tool import delete_file
    from tools.move_file_tool import move_file
    from tools.copy_file_tool import copy_file
    from tools.replace_in_files_tool import replace_in_files

    mcp.add_tool(write_file)
    mcp.add_tool(edit_file)
    mcp.add_tool(delete_file)
    mcp.add_tool(move_file)
    mcp.add_tool(copy_file)
    mcp.add_tool(replace_in_files)

    if not config.WRITE_ALLOWED_ROOTS:
        logger.warning(
            "Write tools are ENABLED, but WRITE_ALLOWED_ROOTS is empty. "
            "All write operations will be refused until allowed roots are configured."
        )
    else:
        logger.warning(
            f"Write tools are ENABLED with allowed roots: {config.WRITE_ALLOWED_ROOTS}"
        )
    logger.info(
        "Registered write tools: write_file, edit_file, delete_file, move_file, copy_file, replace_in_files."
    )
else:
    logger.info("Write tools are disabled (ENABLE_WRITE_TOOLS=false).")

# Conditionally Register Git Integration Tools
if config.ENABLE_GIT_TOOLS:
    from services.confirmation_service import ApprovalGate, ConfirmationService
    from services.git_service import GitService
    from tools.git_tools import register_git_tools

    git_service = GitService(
        config.PROJECT_ROOT,
        timeout=config.GIT_COMMAND_TIMEOUT_SECONDS,
        max_diff_lines=config.GIT_MAX_DIFF_LINES,
        block_ignored=config.BLOCK_WRITES_TO_IGNORED,
    )
    gate = ApprovalGate(ConfirmationService(config.GIT_CONFIRM_TTL_SECONDS), mode=config.GIT_CONFIRM_MODE)
    register_git_tools(mcp, git_service, gate, enable_write_tools=config.ENABLE_WRITE_TOOLS)
    logger.info(f"Registered Git tools (write_enabled={config.ENABLE_WRITE_TOOLS}).")

# Conditionally Register Automated Verification Tools
if config.ENABLE_VERIFICATION_TOOLS:
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

