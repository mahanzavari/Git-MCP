import subprocess
import os
from typing import List, Dict, Any
from utils import is_safe_path, truncate_output, slice_lines

class GitEngine:
    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        if not os.path.isdir(os.path.join(self.repo_path, ".git")):
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _run(self, args: List[str]) -> str:
        """Executes git command securely."""
        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
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

    # --- Exploration Tools (New) ---

    def get_file_tree(self, max_depth: int = 2) -> str:
        """
        Returns a visual tree of files tracked by git.
        Using 'git ls-files' ensures we respect .gitignore.
        """
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
                # Check if it's a leaf (file) or branch (dir)
                is_file = len(node[key]) == 0
                prefix = "  " * depth + ("📄 " if is_file else "Qs ")
                output.append(f"{prefix}{key}")
                if not is_file:
                    output.append(render_tree(node[key], depth + 1))
            return "\n".join(filter(None, output))

        return render_tree(tree_structure)

    def search_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Uses git grep to find definitions of classes or functions.
        """
        # Look for 'class Symbol' or 'def Symbol'
        # -n: line number, -E: extended regex
        query = f"(class|def) {symbol}"
        raw = self._run(["grep", "-n", "-E", query])
        
        results = []
        if "Error" in raw or not raw:
            return []

        for line in raw.splitlines():
            try:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    results.append({
                        "file": parts[0],
                        "line": int(parts[1]),
                        "context": parts[2].strip()
                    })
            except ValueError:
                continue
        return results

    # --- Standard Git Operations (Preserved) ---
    
    def get_status(self) -> Dict[str, Any]:
        raw = self._run(["status", "--porcelain"])
        staged, modified, untracked = [], [], []
        for line in raw.splitlines():
            if not line: continue
            code, path = line[:2], line[3:].strip()
            if code[0] in "MADRC": staged.append(path)
            if code[1] in "MADRC": modified.append(path)
            if code.startswith("??"): untracked.append(path)
        return {
            "branch": self._run(["rev-parse", "--abbrev-ref", "HEAD"]),
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

    def stage_files(self, files: List[str]) -> str:
        return self._run(["add"] + files)

    def commit_changes(self, message: str) -> str:
        return self._run(["commit", "-m", message])
    
    def smart_diff(self, target: str = "unstaged") -> Dict[str, Any]:
        args = ["diff"]
        if target == "staged": args.append("--staged")
        elif target != "unstaged": args.append(target)
        raw = self._run(args)
        return {"diff": truncate_output(raw, 6000)["content"]}