from mcp.server.fastmcp import FastMCP
from git_engine import GitEngine
import os
import sys

mcp = FastMCP("git-mcp")

REPO_PATH = os.getenv("GIT_REPO_PATH", ".")
try:
    git = GitEngine(REPO_PATH)
except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

# --- Read Tools ---

@mcp.tool()
def get_repo_status() -> dict:
    return git.get_status()

@mcp.tool()
def search_code(query: str) -> dict:
    results = git.search_repo(query)
    return {"query": query, "matches": len(results), "results": results}

@mcp.tool()
def read_file(path: str, start_line: int = 1, end_line: int = 100) -> dict:
    return git.read_file(path, start_line, end_line)

@mcp.tool()
def get_commit_history(limit: int = 10) -> dict:
    return {"commits": git.get_history(limit)}

@mcp.tool()
def view_diff(target: str = "unstaged") -> dict:
    return git.smart_diff(target)

@mcp.tool()
def list_branches() -> str:
    return git.list_branches()

# --- Write Tools ---

@mcp.tool()
def git_add(files: list[str]) -> str:
    return git.stage_files(files)

@mcp.tool()
def git_commit(message: str) -> str:
    return git.commit_changes(message)

@mcp.tool()
def git_checkout_new_branch(branch_name: str) -> str:
    return git.create_branch(branch_name)

@mcp.tool()
def git_checkout_existing_branch(branch_name: str) -> str:
    return git.checkout_branch(branch_name)

@mcp.tool()
def git_reset(mode: str = "mixed") -> str:
    return git.reset_changes(mode)

@mcp.tool()
def git_push(remote: str = "origin") -> str:
    return git.push_changes(remote)

@mcp.tool()
def git_pull(remote: str = "origin") -> str:
    return git.pull_changes(remote)

# --- Stash Tools ---

@mcp.tool()
def git_stash_save(message: str = None, include_untracked: bool = False) -> str:
    """
    Stash local changes to clean the working directory.
    Args:
        message: Optional description of the stash.
        include_untracked: If True, stashes untracked files as well.
    """
    return git.stash_save(message, include_untracked)

@mcp.tool()
def git_stash_pop(index: int = 0) -> str:
    """
    Apply and remove the top stash (or a specific index) from the stack.
    Args:
        index: The index of the stash to pop (default 0 is the latest).
    """
    return git.stash_pop(index)

@mcp.tool()
def git_stash_list() -> str:
    """List all stashed changes available."""
    return git.stash_list()

@mcp.tool()
def git_stash_clear() -> str:
    """WARNING: Removes all stashed entries permanently."""
    return git.stash_clear()

if __name__ == "__main__":
    mcp.run()