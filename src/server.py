from mcp.server.fastmcp import FastMCP
from git_engine import GitEngine
import os
import sys

# Initialize the Server
# We name it "git-mcp"
mcp = FastMCP("git-mcp")

# Initialize Git Engine pointing to current working directory
# In a real app, you might pass the path via env var or arguments
REPO_PATH = os.getenv("GIT_REPO_PATH", ".")
try:
    git = GitEngine(REPO_PATH)
except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

@mcp.tool()
def get_repo_status() -> dict:
    """
    Get the current status of the repository (branches, dirty state).
    Use this first to see what branch you are on.
    """
    return git.get_status()

@mcp.tool()
def search_code(query: str) -> dict:
    """
    Search for a string or pattern across the entire repository.
    Returns file paths and code snippets.
    Useful to find WHERE code is located.
    """
    results = git.search_repo(query)
    return {
        "query": query,
        "matches_found": len(results),
        "results": results
    }

@mcp.tool()
def read_file(path: str, start_line: int = 1, end_line: int = 100) -> dict:
    """
    Read the contents of a specific file.
    Supports pagination to save context window.
    """
    return git.read_file(path, start_line, end_line)

@mcp.tool()
def get_commit_history(limit: int = 10) -> dict:
    """
    Get the latest commit log.
    """
    return {"commits": git.get_history(limit)}

@mcp.tool()
def view_diff(target: str = "LOCAL") -> dict:
    """
    View changes.
    - target="LOCAL": Shows uncommitted changes (working dir vs HEAD).
    - target="<commit_hash>": Shows changes in that commit.
    """
    return git.smart_diff(target)

if __name__ == "__main__":
    # This runs the server over Stdio (Standard Input/Output)
    # The MCP client (Claude, or your custom script) will attach to this process.
    mcp.run()