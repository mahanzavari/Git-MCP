use std::path::{Path, PathBuf};
use std::process::Command;
use std::{env, fs, io};

pub struct GitEngine {
    pub repo_path: PathBuf,
}

impl GitEngine {
    /// Initialize: Find existing .git up the tree, or init new one in CWD
    pub fn new() -> io::Result<Self> {
        let cwd = env::current_dir()?;
        let root = Self::find_git_root(&cwd).unwrap_or_else(|| {
            println!("No git repo found. Initializing in {:?}", cwd);
            let _ = Command::new("git").arg("init").current_dir(&cwd).output();
            cwd.clone()
        });
        
        Ok(Self { repo_path: root })
    }

    fn find_git_root(start: &Path) -> Option<PathBuf> {
        let mut current = start.to_path_buf();
        loop {
            if current.join(".git").exists() {
                return Some(current);
            }
            if !current.pop() {
                return None;
            }
        }
    }

    fn run(&self, args: &[&str]) -> Result<String, String> {
        let output = Command::new("git")
            .args(args)
            .current_dir(&self.repo_path)
            .env("GIT_TERMINAL_PROMPT", "0")
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            // Git sometimes prints to stderr even on success (e.g., push info)
            let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            if stdout.is_empty() { Ok(stderr) } else { Ok(stdout) }
        } else {
            Err(String::from_utf8_lossy(&output.stderr).trim().to_string())
        }
    }

    // --- File Operations (Needed for Conflict Resolution) ---

    pub fn read_file(&self, rel_path: &str) -> String {
        let full_path = self.repo_path.join(rel_path);
        if !full_path.starts_with(&self.repo_path) {
            return "Error: Access denied (path traversal)".to_string();
        }
        match fs::read_to_string(full_path) {
            Ok(c) => c,
            Err(e) => format!("Error reading file: {}", e),
        }
    }

    pub fn write_file(&self, rel_path: &str, content: &str) -> String {
        let full_path = self.repo_path.join(rel_path);
        if !full_path.starts_with(&self.repo_path) {
            return "Error: Access denied (path traversal)".to_string();
        }
        // Ensure parent directory exists
        if let Some(parent) = full_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        match fs::write(full_path, content) {
            Ok(_) => format!("Successfully wrote to {}", rel_path),
            Err(e) => format!("Error writing file: {}", e),
        }
    }

    // --- Core Git Tools ---

    pub fn get_file_tree(&self, max_depth: usize) -> String {
        let output = self.run(&["ls-files"]).unwrap_or_default();
        let files: Vec<&str> = output.lines().collect();
        
        let mut result = String::new();
        let root_str = self.repo_path.file_name().unwrap().to_string_lossy();
        result.push_str(&format!("📂 {}/\n", root_str));

        for file in files.iter().take(50) {
            let depth = file.matches('/').count();
            if depth < max_depth {
                let indent = "  ".repeat(depth + 1);
                result.push_str(&format!("{}📄 {}\n", indent, file));
            }
        }
        if files.len() > 50 { result.push_str("  ... (truncated)\n"); }
        result
    }

    pub fn status(&self) -> String {
        let s = self.run(&["status"]).unwrap_or_default();
        if s.is_empty() { "Clean working directory".to_string() } else { s }
    }

    pub fn diff(&self, target: &str) -> String {
        let mut args = vec!["diff"];
        if target == "staged" { args.push("--staged"); }
        else if target != "unstaged" { args.push(target); }
        
        let out = self.run(&args).unwrap_or_else(|e| e);
        if out.len() > 3000 {
            format!("{}\n...[Diff truncated to 3000 chars]", &out[..3000])
        } else {
            out
        }
    }

    pub fn commit(&self, msg: &str) -> String {
        self.run(&["commit", "-m", msg]).unwrap_or_else(|e| e)
    }

    pub fn add(&self, files: Vec<String>) -> String {
        let mut args = vec!["add"];
        if files.is_empty() || (files.len() == 1 && files[0] == ".") {
             args.push(".");
        } else {
            args.extend(files.iter().map(|s| s.as_str()));
        }
        self.run(&args).unwrap_or_else(|e| e)
    }

    // --- Advanced Operations ---

    pub fn log(&self, count: usize) -> String {
        let count_str = format!("-{}", count);
        self.run(&["log", "--oneline", &count_str, "--graph", "--decorate"]).unwrap_or_else(|e| e)
    }

    pub fn checkout(&self, branch: &str, create: bool) -> String {
        let mut args = vec!["checkout"];
        if create { args.push("-b"); }
        args.push(branch);
        self.run(&args).unwrap_or_else(|e| e)
    }

    pub fn push(&self, remote: &str, branch: &str) -> String {
        // e.g. git push origin main
        self.run(&["push", remote, branch]).unwrap_or_else(|e| e)
    }

    pub fn pull(&self, remote: &str, branch: &str) -> String {
        // e.g. git pull origin main
        self.run(&["pull", remote, branch]).unwrap_or_else(|e| e)
    }

    pub fn merge(&self, branch: &str) -> String {
        // Returns error if conflict occurs
        match self.run(&["merge", branch]) {
            Ok(out) => out,
            Err(e) => format!("Merge failed (Conflict?): {}", e),
        }
    }

    pub fn stash(&self, action: &str) -> String {
        match action {
            "pop" => self.run(&["stash", "pop"]).unwrap_or_else(|e| e),
            "list" => self.run(&["stash", "list"]).unwrap_or_else(|e| e),
            _ => self.run(&["stash"]).unwrap_or_else(|e| e), // default push
        }
    }

    pub fn reset(&self, target: &str, hard: bool) -> String {
        let mut args = vec!["reset"];
        if hard { args.push("--hard"); }
        args.push(target);
        self.run(&args).unwrap_or_else(|e| e)
    }
    
    pub fn branch_list(&self) -> String {
        self.run(&["branch", "-vv"]).unwrap_or_else(|e| e)
    }
}