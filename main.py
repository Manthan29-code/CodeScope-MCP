import sys
import config
from utils.logger import logger
from server import mcp

if __name__ == "__main__":
    logger.info(f"Starting CodeScope MCP Server on {config.HOST}:{config.PORT}...")
    try:
        mcp.run(transport="streamable-http", host=config.HOST, port=config.PORT)
    except KeyboardInterrupt:
        logger.info("CodeScope MCP Server stopped by user.")
        sys.exit(0)
