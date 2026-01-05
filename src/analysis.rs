use std::fs;
use std::path::{Path, PathBuf};
use md5;
use tree_sitter::{Parser, Query, QueryCursor, Language};

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

        // Cache Key = MD5(Content + Path) 
        // We include path to ensure extension-based logic doesn't clash
        let hash = format!("{:x}", md5::compute(format!("{}{}", rel_path, content)));
        let cache_file = self.cache_dir.join(format!("{}.skel", hash));

        if cache_file.exists() {
            return fs::read_to_string(cache_file).unwrap_or_default();
        }

        let skeleton = self.generate_skeleton(&content, rel_path);
        let _ = fs::write(cache_file, &skeleton); 
        skeleton
    }

    fn generate_skeleton(&self, content: &str, path: &str) -> String {
        let extension = Path::new(path)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("");

        match extension {
            "rs" => self.process_tree_sitter(content, tree_sitter_rust::language(), 
                // Rust: Fold function bodies, impl bodies, and mod blocks
                r#"
                (function_item body: (block) @body)
                (impl_item body: (block) @body)
                (mod_item body: (block) @body)
                "#, " ... "),
            
            "py" => self.process_tree_sitter(content, tree_sitter_python::language(), 
                // Python: Fold function and class bodies
                r#"
                (function_definition body: (block) @body)
                (class_definition body: (block) @body)
                "#, " ..."),

            "js" | "ts" | "jsx" | "tsx" => self.process_tree_sitter(content, tree_sitter_javascript::language(), 
                // JS: Method definitions, function declarations
                r#"
                (function_declaration body: (statement_block) @body)
                (method_definition body: (statement_block) @body)
                (class_declaration body: (class_body) @body)
                (arrow_function body: (statement_block) @body)
                "#, " { ... }"),

            "java" => self.process_tree_sitter(content, tree_sitter_java::language(), 
                // Java: Methods and Classes
                r#"
                (method_declaration body: (block) @body)
                (constructor_declaration body: (block) @body)
                (class_declaration body: (class_body) @body)
                "#, " { /* ... */ }"),

            "cpp" | "cc" | "hpp" => self.process_tree_sitter(content, tree_sitter_cpp::language(), 
                // C++: Functions and Structs/Classes
                r#"
                (function_definition body: (compound_statement) @body)
                (struct_specifier body: (field_declaration_list) @body)
                (class_specifier body: (field_declaration_list) @body)
                "#, " { /* ... */ }"),

            "c" | "h" => self.process_tree_sitter(content, tree_sitter_c::language(), 
                r#"
                (function_definition body: (compound_statement) @body)
                "#, " { /* ... */ }"),

            "go" => self.process_tree_sitter(content, tree_sitter_go::language(), 
                r#"
                (function_declaration body: (block) @body)
                (method_declaration body: (block) @body)
                "#, " { ... }"),

            _ => {
                // Fallback: simple truncation for unsupported files
                let lines: Vec<&str> = content.lines().collect();
                if lines.len() > 50 {
                    format!(
                        "{}\n... ({} lines hidden)",
                        lines.iter().take(20).cloned().collect::<Vec<_>>().join("\n"),
                        lines.len() - 20
                    )
                } else {
                    content.to_string()
                }
            }
        }
    }

    fn process_tree_sitter(&self, content: &str, language: Language, query_str: &str, replacement: &str) -> String {
        let mut parser = Parser::new();
        if parser.set_language(language).is_err() {
            return "Error: Failed to load language grammar".to_string();
        }

        let tree = match parser.parse(content, None) {
            Some(t) => t,
            None => return content.to_string(), // Parse failed, return original
        };

        let query = match Query::new(language, query_str) {
            Ok(q) => q,
            Err(e) => return format!("Query Error: {:?}", e),
        };

        let mut query_cursor = QueryCursor::new();
        let matches = query_cursor.matches(&query, tree.root_node(), content.as_bytes());

        // Collect all ranges to be replaced
        let mut ranges: Vec<(usize, usize)> = Vec::new();
        for m in matches {
            for capture in m.captures {
                ranges.push((capture.node.start_byte(), capture.node.end_byte()));
            }
        }

        // Sort ranges and merge overlapping/nested ones
        // (Though strictly, skeletons usually just hit top-level bodies, 
        // sorting ensures we build the string linearly)
        ranges.sort_by(|a, b| a.0.cmp(&b.0));

        let mut result = String::new();
        let mut last_pos = 0;

        for (start, end) in ranges {
            if start < last_pos { continue; } // Handle nested captures safely
            
            // Append code before the body
            result.push_str(&content[last_pos..start]);
            
            // Append replacement
            result.push_str(replacement);

            last_pos = end;
        }

        // Append remaining code
        if last_pos < content.len() {
            result.push_str(&content[last_pos..]);
        }

        result
    }
}