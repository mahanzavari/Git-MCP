import ast
import os
import hashlib
from typing import Optional

class AnalysisEngine:
    def __init__(self, repo_path: str):
        self.repo_path = os.path.abspath(repo_path)
        self.cache_dir = os.path.join(self.repo_path, ".git_agent_cache", "skeletons")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, file_path: str) -> str:
        """Generates a safe cache filename based on the file path hash."""
        # We hash the path to avoid directory structure issues in the cache folder
        path_hash = hashlib.md5(file_path.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{path_hash}.skel")

    def _generate_python_skeleton(self, source: str) -> str:
        """Parses Python source and returns signatures + docstrings only."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return "Error: Syntax Error in file. Cannot generate skeleton."

        skeleton_lines = []
        
        # Helper to handle indentation
        def get_indent(node):
            return "    " * (getattr(node, 'col_offset', 0) // 4)

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Keep imports to understand dependencies
                skeleton_lines.append(ast.get_source_segment(source, node))
            
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                # Get the definition line (e.g., "def foo(x):")
                # This is a simplification; robust extraction handles decorators
                segment = ast.get_source_segment(source, node)
                if not segment: continue
                
                # Extract just the signature (first line-ish)
                sig_lines = segment.splitlines()
                signature = sig_lines[0] 
                
                # Check for decorators
                if node.decorator_list:
                    # Prepend decorators if they exist in source
                    # (Simplified logic: taking lines before the def/class keyword)
                    pass 

                skeleton_lines.append(f"\n{signature}")
                
                # Add Docstring if exists
                docstring = ast.get_docstring(node)
                if docstring:
                    # Truncate long docstrings
                    clean_doc = docstring.split('\n')[0][:80]
                    skeleton_lines.append(f'{get_indent(node)}    """{clean_doc}..."""')
                
                # Add Ellipsis
                skeleton_lines.append(f"{get_indent(node)}    ...")
                
                # For classes, we want to see method signatures inside
                if isinstance(node, ast.ClassDef):
                    for sub_node in node.body:
                        if isinstance(sub_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            sub_sig = ast.get_source_segment(source, sub_node).splitlines()[0]
                            skeleton_lines.append(f"    {sub_sig} ...")

        return "\n".join(skeleton_lines)

    def get_file_skeleton(self, rel_path: str) -> str:
        """
        Returns a compressed view of the file.
        Uses caching to speed up repeated access.
        """
        full_path = os.path.join(self.repo_path, rel_path)
        
        if not os.path.exists(full_path):
            return "Error: File not found."

        # Read File
        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

        # 1. Check Cache Validity
        # We use a hash of the CONTENT to decide if we need to regenerate.
        # This is more robust than timestamps for git operations.
        content_hash = hashlib.md5(content.encode()).hexdigest()
        cache_path = self._get_cache_path(rel_path)
        
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                cached_data = f.read()
                # Format: HASH\nCONTENT
                if cached_data.startswith(content_hash):
                    return cached_data.split('\n', 1)[1]

        # 2. Generate Skeleton
        if rel_path.endswith(".py"):
            skeleton = self._generate_python_skeleton(content)
        else:
            # Fallback for non-python: First 20 lines
            lines = content.splitlines()
            skeleton = "\n".join(lines[:20])
            if len(lines) > 20:
                skeleton += "\n\n... (rest of file truncated) ..."

        # 3. Write Cache
        try:
            with open(cache_path, 'w') as f:
                f.write(f"{content_hash}\n{skeleton}")
        except Exception:
            pass # Non-critical failure

        return skeleton