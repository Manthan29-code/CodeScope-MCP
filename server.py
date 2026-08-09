from fastmcp import FastMCP
from utils.logger import logger
from tools.list_directory_tool import list_directory_tree
from tools.file_metadata_tool import get_file_metadata
from tools.read_file_tool import read_file
from tools.read_multiple_files_tool import read_multiple_files
from tools.search_files_tool import search_files

# Create FastMCP server instance
mcp = FastMCP("CodeScope")

# Register Tools
mcp.add_tool(list_directory_tree)
mcp.add_tool(get_file_metadata)
mcp.add_tool(read_file)
mcp.add_tool(read_multiple_files)
mcp.add_tool(search_files)

logger.info("Registered all CodeScope MCP tools successfully.")
