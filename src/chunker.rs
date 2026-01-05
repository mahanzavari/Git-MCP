use tree_sitter::{Parser, Language, Query, QueryCursor};
use std::path::Path;

pub struct CodeChunk {
    pub path: String,
    pub content: String,
    pub start_line: usize,
    pub end_line: usize,
}

pub struct Chunker;

impl Chunker {
    pub fn chunk(content: &str, path: &str) -> Vec<CodeChunk> {
        let extension = Path::new(path)
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("");

        let (lang, query_str) = match extension {
            "rs" => (tree_sitter_rust::language(), r#"
                (function_item) @item
                (impl_item) @item
                (struct_item) @item
            "#),
            "py" => (tree_sitter_python::language(), r#"
                (function_definition) @item
                (class_definition) @item
            "#),
            "js" | "ts" | "jsx" | "tsx" => (tree_sitter_javascript::language(), r#"
                (function_declaration) @item
                (class_declaration) @item
                (method_definition) @item
            "#),
            "go" => (tree_sitter_go::language(), r#"
                (function_declaration) @item
                (method_declaration) @item
            "#),
             "java" => (tree_sitter_java::language(), r#"
                (method_declaration) @item
                (class_declaration) @item
            "#),
            "cpp" | "cc" | "c" | "h" => (tree_sitter_cpp::language(), r#"
                (function_definition) @item
                (class_specifier) @item
            "#),
            _ => return vec![], // Unsupported files are skipped for semantic search (use raw grep)
        };

        Self::extract_chunks(content, path, lang, query_str)
    }

    fn extract_chunks(content: &str, path: &str, lang: Language, query_str: &str) -> Vec<CodeChunk> {
        let mut parser = Parser::new();
        parser.set_language(lang).ok();

        let tree = match parser.parse(content, None) {
            Some(t) => t,
            None => return vec![],
        };

        let query = Query::new(lang, query_str).expect("Invalid query");
        let mut cursor = QueryCursor::new();
        let matches = cursor.matches(&query, tree.root_node(), content.as_bytes());

        let mut chunks = Vec::new();
        let mut seen_ranges = std::collections::HashSet::new();

        for m in matches {
            for capture in m.captures {
                let node = capture.node;
                let range = (node.start_byte(), node.end_byte());
                
                // Avoid duplicates (nested captures)
                if seen_ranges.contains(&range) { continue; }
                seen_ranges.insert(range);

                // --- Docstring/Comment Extraction ---
                // Look backwards from the node to find immediate preceding comments
                let mut start_byte = node.start_byte();
                let mut prev = node.prev_sibling();
                while let Some(p) = prev {
                    if p.kind().contains("comment") || p.kind() == "string" { // Python docstrings are strings
                        // Check if it's immediately above (allowing for whitespace/newlines)
                        if p.end_byte() < start_byte && (start_byte - p.end_byte()) < 50 { 
                            start_byte = p.start_byte();
                            prev = p.prev_sibling();
                        } else {
                            break;
                        }
                    } else {
                        break;
                    }
                }

                // Extract text
                let chunk_text = &content[start_byte..node.end_byte()];
                let start_line = content[..start_byte].lines().count();
                let end_line = content[..node.end_byte()].lines().count();

                // Only index significant chunks (> 3 lines) to reduce noise
                if end_line - start_line > 3 {
                    chunks.push(CodeChunk {
                        path: path.to_string(),
                        content: chunk_text.to_string(),
                        start_line,
                        end_line,
                    });
                }
            }
        }
        chunks
    }
}