import subprocess
import os
from typing import List, Dict, Any, Optional
from utils import is_safe_path, truncate_output, slice_lines

class GitEngine:
    def __init__(self, start_path: str = "."):
        """
        Initializes the GitEngine.
        1. Checks if start_path (or parents) is a git repo.
        2. If found, uses that root.
        3. If NOT found, initializes a NEW git repo at start_path.
        """
        self.start_path = os.path.abspath(start_path)
        self.repo_path = self._resolve_git_root(self.start_path)

        # If no git repo found in tree, initialize one in the start directory
        if not self.repo_path:
            print(f"No git repository found. Initializing in: {self.start_path}")
            self._init_repo(self.start_path)
            self.repo_path = self.start_path

    def _resolve_git_root(self, path: str) -> Optional[str]:
        """Recursive search up the directory tree for .git folder."""
        current = path
        while True:
            if os.path.isdir(os.path.join(current, ".git")):
                return current
            
            parent = os.path.dirname(current)
            if parent == current: # Reached filesystem root
                return None
            current = parent

    def _init_repo(self, path: str):
        """Runs git init."""
        try:
            subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to initialize git repository: {e}")

    def _run(self, args: List[str]) -> str:
        """Executes git command securely."""
        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path, # Always run from the Git Root
                capture_output=True,
                text=True,
                check=True,
                env=env,
                timeout=15
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error ({e.returncode}): {e.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "Error: Git command timed out."

    # --- Exploration Tools ---

    def get_file_tree(self, max_depth: int = 2) -> str:
        """Returns visual tree using git ls-files (respects .gitignore)."""
        raw_files = self._run(["ls-files"]).splitlines()
        
        tree_structure = {}
        for path in raw_files:
            parts = path.split('/')
            current = tree_structure
            for part in parts:
                current = current.setdefault(part, {})

        def render_tree(node, depth=0):
            if depth > max_depth:
                return ""
            output = []
            keys = sorted(node.keys())
            for key in keys:
                is_file = len(node[key]) == 0
                prefix = "  " * depth + ("📄 " if is_file else "📂 ")
                output.append(f"{prefix}{key}")
                if not is_file:
                    output.append(render_tree(node[key], depth + 1))
            return "\n".join(filter(None, output))

        return render_tree(tree_structure)

    def search_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        query = f"(class|def) {symbol}"
        raw = self._run(["grep", "-n", "-E", query])
        results = []
        if "Error" in raw or not raw: return []
        for line in raw.splitlines():
            try:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    results.append({"file": parts[0], "line": int(parts[1]), "context": parts[2].strip()})
            except ValueError: continue
        return results

    # --- Standard Git Operations ---
    
    def get_status(self) -> Dict[str, Any]:
        raw = self._run(["status", "--porcelain"])
        staged, modified, untracked = [], [], []
        for line in raw.splitlines():
            if not line: continue
            code, path = line[:2], line[3:].strip()
            if code[0] in "MADRC": staged.append(path)
            if code[1] in "MADRC": modified.append(path)
            if code.startswith("??"): untracked.append(path)
        
        branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        if "Error" in branch: branch = "No commits yet"

        return {
            "root": self.repo_path,
            "branch": branch,
            "is_dirty": bool(staged or modified or untracked),
            "staged": staged, "modified": modified, "untracked": untracked
        }

    def read_file(self, path: str, start_line: int = 1, end_line: int = 1000) -> Dict[str, Any]:
        if not is_safe_path(self.repo_path, path): return {"error": "Access denied"}
        full = os.path.join(self.repo_path, path)
        if not os.path.exists(full): return {"error": "File not found"}
        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            sliced = slice_lines(content, start_line, end_line)
            return truncate_output(sliced)
        except Exception as e: return {"error": str(e)}

    def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        raw = self._run(["log", f"-n {limit}", "--pretty=format:%h|%an|%ad|%s", "--date=short"])
        history = []
        if "Error" in raw: return [] # Handle empty repo
        for line in raw.splitlines():
            try:
                h, author, date, msg = line.split("|", 3)
                history.append({"hash": h, "author": author, "date": date, "message": msg})
            except ValueError: continue
        return history

    def smart_diff(self, target: str = "unstaged") -> Dict[str, Any]:
        args = ["diff"]
        if target == "staged": args.append("--staged")
        elif target != "unstaged": args.append(target)
        raw = self._run(args)
        return {"diff": truncate_output(raw, 6000)["content"]}

    def stage_files(self, files: List[str]) -> str:
        return self._run(["add"] + files)

    def commit_changes(self, message: str) -> str:
        return self._run(["commit", "-m", message])
    
    def create_branch(self, branch_name: str) -> str:
        return self._run(["checkout", "-b", branch_name])

    def checkout_branch(self, branch_name: str) -> str:
        return self._run(["checkout", branch_name])

    def list_branches(self) -> str:
        return self._run(["branch", "--list"])

    def reset_changes(self, mode: str = "mixed") -> str:
        return self._run(["reset", f"--{mode}", "HEAD"])

    def push_changes(self, remote: str = "origin", branch: str = None) -> str:
        if not branch: branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return self._run(["push", remote, branch])

    def pull_changes(self, remote: str = "origin", branch: str = None) -> str:
        if not branch: branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return self._run(["pull", remote, branch])

    # --- Stash ---
    def stash_save(self, msg: str = None, untracked: bool = False) -> str:
        args = ["stash", "push"]
        if untracked: args.append("-u")
        if msg: args.extend(["-m", msg])
        return self._run(args)
    
    def stash_pop(self, idx: int = 0) -> str: return self._run(["stash", "pop", f"stash@{{{idx}}}"])
    def stash_list(self) -> str: return self._run(["stash", "list"])
    def stash_clear(self) -> str: return self._run(["stash", "clear"])