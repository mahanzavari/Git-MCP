from mcp.server.fastmcp import FastMCP
import os
import argparse
from .git_engine import GitEngine

# Initialize the MCP Server
mcp = FastMCP("Git-MCP-Server")

# Global engine instance (will be set in main)
git_engine: GitEngine = None

@mcp.tool()
def get_repo_summary() -> dict:
    """
    Get a high-level overview of the repository status, current branch, 
    and dirty state (uncommitted changes).
    """
    return git_engine.get_status()

@mcp.tool()
def list_files(directory: str = ".") -> str:
    """
    List files in a directory (recursively, ignoring .git). 
    Useful to explore the structure.
    """
    # Simple ls-files wrapper
    # We use ls-files because it respects .gitignore automatically
    return git_engine._run_git(["ls-files", directory])

@mcp.tool()
def search_repository(query: str) -> list:
    """
    Search for a string or pattern across the entire codebase.
    Returns file paths and line numbers with snippets.
    
    Args:
        query: The string or regex to search for.
    """
    return git_engine.search_repo(query)

@mcp.tool()
def read_file_segment(path: str, start_line: int = 1, end_line: int = -1) -> dict:
    """
    Read the content of a file. Supports pagination to save context window.
    
    Args:
        path: Relative path to the file.
        start_line: Line number to start reading from (1-based).
        end_line: Line number to stop at. Use -1 for end of file.
    """
    return git_engine.get_file_content(path, start_line, end_line)

@mcp.tool()
def get_commit_history(limit: int = 10) -> list:
    """
    Get the recent commit log.
    """
    return git_engine.get_log(limit)

@mcp.tool()
def smart_diff(target: str = "HEAD") -> dict:
    """
    Get the diff between the current working directory and a target (default HEAD).
    Output is truncated if too large to prevent context overflow.
    """
    return git_engine.get_smart_diff(target)

def main():
    global git_engine
    
    # Simple CLI to point to the repo
    parser = argparse.ArgumentParser(description="Git MCP Server")
    parser.add_argument("--repo", type=str, default=".", help="Path to the git repository")
    args = parser.parse_args()

    try:
        git_engine = GitEngine(args.repo)
        print(f"📦 Git MCP Server active for: {git_engine.repo_path}")
        mcp.run()
    except Exception as e:
        print(f"Failed to initialize: {e}")
        exit(1)

if __name__ == "__main__":
    main()