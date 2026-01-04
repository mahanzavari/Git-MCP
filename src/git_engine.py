import subprocess
import os
from typing import List, Dict, Any, Union
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

    # --- Read / Status Operations ---

    def get_status(self) -> Dict[str, Any]:
        """Detailed status including branch, staged, modified, and untracked."""
        raw = self._run(["status", "--porcelain"])
        staged, modified, untracked = [], [], []
        
        for line in raw.splitlines():
            if not line: continue
            code = line[:2]
            path = line[3:].strip()
            
            if code[0] in "MADRC": staged.append(path)
            if code[1] in "MADRC": modified.append(path)
            if code.startswith("??"): untracked.append(path)

        branch_info = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        
        return {
            "current_branch": branch_info,
            "is_dirty": bool(staged or modified or untracked),
            "staged_files": staged,
            "modified_unstaged_files": modified,
            "untracked_files": untracked
        }

    def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        raw = self._run(["log", f"-n {limit}", "--pretty=format:%h|%an|%ad|%s", "--date=short"])
        history = []
        if "Error" in raw: return []
        for line in raw.splitlines():
            try:
                h, author, date, msg = line.split("|", 3)
                history.append({"hash": h, "author": author, "date": date, "message": msg})
            except ValueError:
                continue
        return history

    def search_repo(self, query: str) -> List[Dict[str, Any]]:
        raw = self._run(["grep", "-n", "-I", query])
        results = []
        if "Error" in raw or not raw: return []

        for line in raw.splitlines()[:50]:
            try:
                parts = line.split(":", 2)
                if len(parts) == 3:
                    results.append({"file": parts[0], "line": int(parts[1]), "content": parts[2].strip()})
            except ValueError:
                continue
        return results

    def read_file(self, path: str, start_line: int = 1, end_line: int = 1000) -> Dict[str, Any]:
        if not is_safe_path(self.repo_path, path):
            return {"error": "Access denied: Path outside repository"}
        
        full_path = os.path.join(self.repo_path, path)
        if not os.path.exists(full_path):
            return {"error": "File not found"}

        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            sliced = slice_lines(content, start_line, end_line)
            result = truncate_output(sliced)
            return {"path": path, "content": result["content"], "truncated": result["truncated"]}
        except Exception as e:
            return {"error": str(e)}

    def smart_diff(self, target: str = "unstaged") -> Dict[str, Any]:
        args = ["diff"]
        if target == "staged":
            args.append("--staged")
        elif target != "unstaged":
            args.append(target)
            
        raw_diff = self._run(args)
        
        return {
            "target": target,
            "diff_preview": truncate_output(raw_diff, max_chars=6000)["content"]
        }

    # --- Write / State Operations ---

    def stage_files(self, files: List[str]) -> str:
        for f in files:
            if not is_safe_path(self.repo_path, f) and f != ".":
                return f"Error: Invalid path {f}"
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
        if mode not in ["soft", "mixed", "hard"]:
            return "Error: Invalid reset mode."
        return self._run(["reset", f"--{mode}", "HEAD"])

    # --- Remote Operations ---

    def push_changes(self, remote: str = "origin", branch: str = None) -> str:
        if not branch:
            branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return self._run(["push", remote, branch])

    def pull_changes(self, remote: str = "origin", branch: str = None) -> str:
        if not branch:
             branch = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return self._run(["pull", remote, branch])

    # --- Stash Operations ---

    def stash_save(self, message: str = None, include_untracked: bool = False) -> str:
        """Stashes changes."""
        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if message:
            args.extend(["-m", message])
        
        return self._run(args)

    def stash_pop(self, index: int = 0) -> str:
        """Pops a specific stash (default 0)."""
        return self._run(["stash", "pop", f"stash@{{{index}}}"])

    def stash_list(self) -> str:
        """Lists stashes."""
        return self._run(["stash", "list"])
    
    def stash_clear(self) -> str:
        """Removes all stashed entries."""
        return self._run(["stash", "clear"])