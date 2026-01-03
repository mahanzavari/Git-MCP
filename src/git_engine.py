import subprocess
import os
import re
from typing import List, Dict, Any, Optional
from utils import is_safe_path, truncate_output, slice_lines

class GitEngine:
    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        if not os.path.isdir(os.path.join(self.repo_path, ".git")):
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _run(self, args: List[str]) -> str:
        """
        Executes git command securely (shell=False).
        """
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                # Prevent hanging on massive outputs
                timeout=10 
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error running git command: {e.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Git command timed out."

    def get_status(self) -> Dict[str, Any]:
        """Parses 'git status --porcelain' into structured JSON."""
        raw = self._run(["status", "--porcelain"])
        staged, modified, untracked = [], [], []
        
        for line in raw.splitlines():
            if not line: continue
            code, path = line[:2], line[3:]
            
            if code[0] in "MADRC": staged.append(path)
            if code[1] in "MADRC": modified.append(path)
            if code.startswith("??"): untracked.append(path)

        return {
            "branch": self._run(["rev-parse", "--abbrev-ref", "HEAD"]),
            "staged": staged,
            "modified_unstaged": modified,
            "untracked": untracked
        }

    def search_repo(self, query: str) -> List[Dict[str, Any]]:
        """Wraps 'git grep' to find code patterns."""
        # -n: line numbers, -I: ignore binary
        raw = self._run(["grep", "-n", "-I", query])
        
        results = []
        if "Error" in raw: return [] # No matches or error

        for line in raw.splitlines()[:50]: # Limit to 50 matches for token safety
            try:
                # Format: file:line:content
                parts = line.split(":", 2)
                if len(parts) == 3:
                    results.append({
                        "file": parts[0],
                        "line": int(parts[1]),
                        "content": parts[2].strip()
                    })
            except ValueError:
                continue
        
        return results

    def read_file(self, path: str, start_line: int = 1, end_line: int = 1000) -> Dict[str, Any]:
        """Reads file content from the filesystem (handling dirty state)."""
        if not is_safe_path(self.repo_path, path):
            return {"error": "Access denied: Path outside repository"}

        full_path = os.path.join(self.repo_path, path)
        
        if not os.path.exists(full_path):
            return {"error": "File not found"}

        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Slice and Truncate
            sliced = slice_lines(content, start_line, end_line)
            result = truncate_output(sliced)
            
            return {
                "path": path,
                "lines_requested": f"{start_line}-{end_line}",
                "content": result["content"],
                "truncated": result["truncated"]
            }
        except Exception as e:
            return {"error": str(e)}

    def get_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Gets concise commit log."""
        raw = self._run(["log", f"-n {limit}", "--pretty=format:%h|%an|%ad|%s", "--date=short"])
        history = []
        for line in raw.splitlines():
            try:
                h, author, date, msg = line.split("|", 3)
                history.append({
                    "hash": h,
                    "author": author,
                    "date": date,
                    "message": msg
                })
            except ValueError:
                continue
        return history

    def smart_diff(self, target: str = "HEAD") -> Dict[str, Any]:
        """
        Gets the diff of a commit OR the working directory.
        """
        if target == "LOCAL":
            # Diff between staging/working and HEAD
            raw_diff = self._run(["diff", "HEAD"])
        else:
            raw_diff = self._run(["show", target])
        
        # Simple stats parsing
        files_changed = raw_diff.count("diff --git")
        
        return {
            "target": target,
            "files_changed_count": files_changed,
            "diff_preview": truncate_output(raw_diff, max_chars=8000)["content"]
        }