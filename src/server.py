from mcp.server.fastmcp import FastMCP
from git_engine import GitEngine
from analysis_engine import AnalysisEngine
import os
import sys
import logging

# --- SILENCE NOISE ---
# Set logging to ERROR only to prevent FastMCP INFO logs 
# from leaking into the CLI client via stderr.
logging.basicConfig(level=logging.ERROR)
# ---------------------

# Initialize the Server
mcp = FastMCP("git-mcp")

# Initialize Engines
REPO_PATH = os.getenv("GIT_REPO_PATH", ".")

try:
    # The 'Hard Drive' (Git Operations)
    git = GitEngine(REPO_PATH)
    # The 'X-Ray' (Code Analysis & Caching)
    analyzer = AnalysisEngine(REPO_PATH)
except ValueError as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

# ==============================================================================
# GROUP 1: EXPLORATION & ANALYSIS (The "Map, Index, Zoom" Strategy)
# ==============================================================================

@mcp.tool()
def get_project_structure(max_depth: int = 2) -> str:
    """
    PHASE 1: Returns the file tree of the project.
    Use this FIRST to understand the directory layout and architecture.
    """
    return git.get_file_tree(max_depth)

@mcp.tool()
def inspect_file_interface(path: str) -> str:
    """
    PHASE 2: Returns the 'skeleton' of a file (classes, functions, docstrings).
    Use this to understand a file's capabilities without reading 1000s of lines.
    This is token-efficient and cached.
    """
    return analyzer.get_file_skeleton(path)

@mcp.tool()
def find_symbol_definition(symbol: str) -> list:
    """
    PHASE 3: Locate where a specific class or function is defined across the repo.
    Returns file paths and line numbers.
    """
    return git.search_symbol(symbol)

# ==============================================================================
# GROUP 2: READ & STATUS OPERATIONS
# ==============================================================================

@mcp.tool()
def get_repo_status() -> dict:
    """
    Check current branch, staged files, modified files, and untracked files.
    Always run this before committing.
    """
    return git.get_status()

@mcp.tool()
def search_code(query: str) -> dict:
    """
    Find specific string patterns (content) in the codebase using 'git grep'.
    Useful for finding usage examples of a function.
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
    Read the actual content of a file.
    Use this ONLY after inspecting the interface if you need implementation details.
    """
    return git.read_file(path, start_line, end_line)

@mcp.tool()
def get_commit_history(limit: int = 10) -> dict:
    """Get the recent commit log."""
    return {"commits": git.get_history(limit)}

@mcp.tool()
def view_diff(target: str = "unstaged") -> dict:
    """
    View changes.
    - target="unstaged": Changes in working directory (not added yet).
    - target="staged": Changes added to index (ready to commit).
    - target="HEAD~1": Changes in last commit.
    """
    return git.smart_diff(target)

@mcp.tool()
def list_branches() -> str:
    """List all local branches."""
    return git.list_branches()

# ==============================================================================
# GROUP 3: WRITE & STATE OPERATIONS
# ==============================================================================

@mcp.tool()
def git_add(files: list[str]) -> str:
    """
    Stage files for commit.
    Args:
        files: List of file paths (e.g. ["src/main.py"]) or ["."] for all.
    """
    return git.stage_files(files)

@mcp.tool()
def git_commit(message: str) -> str:
    """
    Commit currently staged changes.
    Args:
        message: The commit message.
    """
    return git.commit_changes(message)

@mcp.tool()
def git_checkout_new_branch(branch_name: str) -> str:
    """Create and switch to a new branch (git checkout -b)."""
    return git.create_branch(branch_name)

@mcp.tool()
def git_checkout_existing_branch(branch_name: str) -> str:
    """Switch to an existing branch."""
    return git.checkout_branch(branch_name)

@mcp.tool()
def git_reset(mode: str = "mixed") -> str:
    """
    Unstage or undo changes.
    Args:
        mode: 'mixed' (default, unstage files), 'hard' (discard all changes).
    """
    return git.reset_changes(mode)

@mcp.tool()
def git_push(remote: str = "origin") -> str:
    """Push current branch to remote."""
    return git.push_changes(remote)

@mcp.tool()
def git_pull(remote: str = "origin") -> str:
    """Pull latest changes from remote."""
    return git.pull_changes(remote)

# ==============================================================================
# GROUP 4: STASH OPERATIONS
# ==============================================================================

@mcp.tool()
def git_stash_save(message: str = None, include_untracked: bool = False) -> str:
    """
    Stash local changes to clean the working directory.
    Args:
        message: Optional description.
        include_untracked: If True, stashes untracked files as well.
    """
    return git.stash_save(message, include_untracked)

@mcp.tool()
def git_stash_pop(index: int = 0) -> str:
    """
    Apply and remove the top stash (or specific index).
    Args:
        index: Default 0 (latest stash).
    """
    return git.stash_pop(index)

@mcp.tool()
def git_stash_list() -> str:
    """List all stashed changes."""
    return git.stash_list()

@mcp.tool()
def git_stash_clear() -> str:
    """WARNING: Removes all stashed entries permanently."""
    return git.stash_clear()

if __name__ == "__main__":
    mcp.run()