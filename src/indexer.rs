use std::fs;
use std::path::{Path, PathBuf};
use serde::{Deserialize, Serialize};
use fastembed::{TextEmbedding, InitOptions, EmbeddingModel};
use rayon::prelude::*;
use crate::chunker::{Chunker, CodeChunk};
use colored::*;

#[derive(Serialize, Deserialize, Clone)]
pub struct IndexedDoc {
    pub path: String,
    pub content: String,
    pub start_line: usize,
    pub embedding: Vec<f32>,
}

pub struct SemanticIndexer {
    model: TextEmbedding,
    index: Vec<IndexedDoc>,
    cache_path: PathBuf,
}

impl SemanticIndexer {
    pub fn new(repo_root: PathBuf) -> Self {
        let cache_dir = repo_root.join(".git_agent_cache");
        fs::create_dir_all(&cache_dir).unwrap_or_default();
        let cache_path = cache_dir.join("embeddings.json");

        println!("{}", "🔄 Initializing Embedding Model (may download ~300MB on first run)...".yellow());
        let model = TextEmbedding::try_new(InitOptions {
            model_name: EmbeddingModel::AllMiniLML6V2,
            show_download_progress: true,
            ..Default::default()
        }).expect("Failed to load embedding model");

        // Load existing index
        let index = if cache_path.exists() {
            let data = fs::read_to_string(&cache_path).unwrap_or_default();
            serde_json::from_str(&data).unwrap_or_else(|_| Vec::new())
        } else {
            Vec::new()
        };

        Self { model, index, cache_path }
    }

    /// Scans the repo and indexes new/modified files
    pub fn index_repo(&mut self, git_engine: &crate::git::GitEngine) {
        let files_str = git_engine.get_file_tree(10); // Get flat list
        // Parse the tree output to get real paths (simplified here, in prod use git ls-files direct)
        let output = git_engine.run(&["ls-files"]).unwrap_or_default();
        let files: Vec<String> = output.lines().map(|s| s.to_string()).collect();

        println!("{}", format!("🔍 Scanning {} files for semantic index...", files.len()).cyan());

        // Identify files that need indexing (naively re-index all for MVP to ensure freshness)
        // In prod: Check file mtimes or hashes against a metadata store.
        
        let chunks: Vec<CodeChunk> = files.par_iter()
            .flat_map(|path| {
                let full_content = git_engine.read_file(path);
                if full_content.starts_with("Error") { return vec![]; }
                Chunker::chunk(&full_content, path)
            })
            .collect();

        if chunks.is_empty() { return; }

        println!("{}", format!("🧠 Embedding {} code chunks...", chunks.len()).cyan());

        let contents: Vec<String> = chunks.iter()
            .map(|c| format!("File: {}\nLine: {}\n\n{}", c.path, c.start_line, c.content))
            .collect();

        // Generate embeddings in batches
        let embeddings = self.model.embed(contents.clone(), None).expect("Embedding failed");

        // Update Index (Rewrite completely for MVP simplicity)
        self.index = chunks.into_iter().zip(embeddings.into_iter()).map(|(chunk, emb)| {
            IndexedDoc {
                path: chunk.path,
                content: chunk.content,
                start_line: chunk.start_line,
                embedding: emb,
            }
        }).collect();

        self.save();
        println!("{}", "✅ Semantic Index Updated".green());
    }

    fn save(&self) {
        let json = serde_json::to_string(&self.index).unwrap();
        let _ = fs::write(&self.cache_path, json);
    }

    pub fn search(&self, query: &str, limit: usize) -> String {
        if self.index.is_empty() {
            return "Index is empty. Run initialization.".to_string();
        }

        let query_embedding = self.model.embed(vec![query.to_string()], None).unwrap().remove(0);

        let mut scored_docs: Vec<(f32, &IndexedDoc)> = self.index.iter().map(|doc| {
            let score = cosine_similarity(&query_embedding, &doc.embedding);
            (score, doc)
        }).collect();

        // Sort descending by score
        scored_docs.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());

        // Format Result
        scored_docs.iter().take(limit).map(|(score, doc)| {
            format!("--- Match (Score: {:.2}) ---\nFile: {}:{}\n\n{}\n", 
                score, doc.path, doc.start_line, doc.content)
        }).collect::<Vec<_>>().join("\n")
    }
}

fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let dot_product: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    dot_product / (norm_a * norm_b)
}