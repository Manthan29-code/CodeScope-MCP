from fastmcp import FastMCP
import config
from utils.logger import logger
from tools.list_directory_tool import list_directory_tree
from tools.file_metadata_tool import get_file_metadata
from tools.read_file_tool import read_file
from tools.read_multiple_files_tool import read_multiple_files
from tools.search_files_tool import search_files

# Create FastMCP server instance
mcp = FastMCP("CodeScope")

# Register Read Tools (always available)
mcp.add_tool(list_directory_tree)
mcp.add_tool(get_file_metadata)
mcp.add_tool(read_file)
mcp.add_tool(read_multiple_files)
mcp.add_tool(search_files)

# Conditionally Register Write Tools (Part 3)
if config.ENABLE_WRITE_TOOLS:
    from tools.write_file_tool import write_file
    from tools.edit_file_tool import edit_file

    mcp.add_tool(write_file)
    mcp.add_tool(edit_file)

    if not config.WRITE_ALLOWED_ROOTS:
        logger.warning(
            "Write tools are ENABLED, but WRITE_ALLOWED_ROOTS is empty. "
            "All write operations will be refused until allowed roots are configured."
        )
    else:
        logger.warning(
            f"Write tools are ENABLED with allowed roots: {config.WRITE_ALLOWED_ROOTS}"
        )
    logger.info("Registered write tools: write_file, edit_file.")
else:
    logger.info("Write tools are disabled (ENABLE_WRITE_TOOLS=false).")
