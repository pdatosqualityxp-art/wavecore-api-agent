from mcp.server.fastmcp import FastMCP

from app.features.conversational_agent.infrastructure.mcp.tools.documents import (
    search_document_chunks,
)
from app.features.conversational_agent.infrastructure.mcp.tools.sales import (
    get_client_summary,
    get_sales_data,
)

mcp = FastMCP("wavecore-data")
mcp.tool()(get_sales_data)
mcp.tool()(get_client_summary)
mcp.tool()(search_document_chunks)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
