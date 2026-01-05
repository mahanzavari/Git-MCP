use std::fs;
use std::path::{Path, PathBuf};
use regex::Regex;
use md5;

pub struct AnalysisEngine {
    cache_dir: PathBuf,
    repo_root: PathBuf,
}

impl AnalysisEngine {
    pub fn new(repo_root: PathBuf) -> Self {
        let cache_dir = repo_root.join(".git_agent_cache");
        fs::create_dir_all(&cache_dir).unwrap_or_default();
        Self { cache_dir, repo_root }
    }

    pub fn get_skeleton(&self, rel_path: &str) -> String {
        let full_path = self.repo_root.join(rel_path);
        
        let content = match fs::read_to_string(&full_path) {
            Ok(c) => c,
            Err(_) => return "Error: File not found".to_string(),
        };

        // Cache Key = MD5(Content)
        let hash = format!("{:x}", md5::compute(&content));
        let cache_file = self.cache_dir.join(format!("{}.skel", hash));

        if cache_file.exists() {
            return fs::read_to_string(cache_file).unwrap_or_default();
        }

        let skeleton = self.generate_skeleton(&content, rel_path);
        let _ = fs::write(cache_file, &skeleton); // Ignore write errors
        skeleton
    }

    fn generate_skeleton(&self, content: &str, path: &str) -> String {
        if path.ends_with(".py") {
            self.python_skeleton(content)
        } else if path.ends_with(".rs") {
            self.rust_skeleton(content)
        } else {
            // Fallback: First 20 lines
            content.lines().take(20).collect::<Vec<_>>().join("\n")
        }
    }

    fn python_skeleton(&self, content: &str) -> String {
        // Simple Regex parser for "def" and "class"
        // In a full implementation, use tree-sitter bindings here.
        let re = Regex::new(r"^\s*(def|class|async def)\s+([a-zA-Z0-9_]+)").unwrap();
        let mut lines = Vec::new();
        
        for line in content.lines() {
            if line.starts_with("import") || line.starts_with("from") {
                lines.push(line.to_string());
            } else if re.is_match(line) {
                lines.push(format!("{} ...", line));
            }
        }
        lines.join("\n")
    }

    fn rust_skeleton(&self, content: &str) -> String {
        let re = Regex::new(r"^\s*(fn|struct|enum|impl|pub fn|pub struct)\s+([a-zA-Z0-9_]+)").unwrap();
        content.lines()
            .filter(|l| re.is_match(l) || l.starts_with("use"))
            .map(|l| if l.starts_with("use") { l.to_string() } else { format!("{} {{ ... }}", l.trim_end_matches('{')) })
            .collect::<Vec<_>>()
            .join("\n")
    }
}