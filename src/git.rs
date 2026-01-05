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
            Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).trim().to_string())
        }
    }

    // --- Tools ---

    pub fn get_file_tree(&self, max_depth: usize) -> String {
        let output = self.run(&["ls-files"]).unwrap_or_default();
        let files: Vec<&str> = output.lines().collect();
        
        // Simple tree renderer
        let mut result = String::new();
        let root_str = self.repo_path.file_name().unwrap().to_string_lossy();
        result.push_str(&format!("📂 {}/\n", root_str));

        // Note: A real tree implementation is complex; simpler list for MVP
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
        let s = self.run(&["status", "--porcelain"]).unwrap_or_default();
        if s.is_empty() { "Clean working directory".to_string() } else { s }
    }

    pub fn diff(&self, target: &str) -> String {
        let mut args = vec!["diff"];
        if target == "staged" { args.push("--staged"); }
        else if target != "unstaged" { args.push(target); }
        
        let out = self.run(&args).unwrap_or_else(|e| e);
        if out.len() > 2000 {
            format!("{}\n...[Diff truncated]", &out[..2000])
        } else {
            out
        }
    }

    pub fn read_file(&self, rel_path: &str) -> String {
        let full_path = self.repo_path.join(rel_path);
        // Security check
        if !full_path.starts_with(&self.repo_path) {
            return "Error: Access denied (path traversal)".to_string();
        }
        match fs::read_to_string(full_path) {
            Ok(c) => c,
            Err(e) => format!("Error reading file: {}", e),
        }
    }

    pub fn commit(&self, msg: &str) -> String {
        self.run(&["commit", "-m", msg]).unwrap_or_else(|e| e)
    }

    pub fn add(&self, files: Vec<String>) -> String {
        let mut args = vec!["add"];
        args.extend(files.iter().map(|s| s.as_str()));
        self.run(&args).unwrap_or_else(|e| e)
    }
}