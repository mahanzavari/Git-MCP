use serde_json::{json, Value};
use crate::git::GitEngine;
use crate::analysis::AnalysisEngine;
use crate::indexer::SemanticIndexer;

pub fn get_tool_definitions() -> Vec<Value> {
    vec![
        // --- Analysis & File System ---
        json!({
            "name": "get_project_structure",
            "description": "See the folder layout (file names only).",
            "parameters": { "type": "object", "properties": { "max_depth": { "type": "integer" } } }
        }),
        json!({
            "name": "inspect_file_interface",
            "description": "See code skeleton (classes/funcs) without reading the whole body.",
            "parameters": { "type": "object", "properties": { "path": { "type": "string" } }, "required": ["path"] }
        }),
        json!({
            "name": "read_file",
            "description": "Read full file content.",
            "parameters": { "type": "object", "properties": { "path": { "type": "string" } }, "required": ["path"] }
        }),
        json!({
            "name": "write_file",
            "description": "Overwrite a file with new content. Use this to resolve merge conflicts or fix code.",
            "parameters": { "type": "object", "properties": { "path": { "type": "string" }, "content": { "type": "string" } }, "required": ["path", "content"] }
        }),

        // --- Git Basics ---
        json!({
            "name": "git_status",
            "description": "Check git status (staged/unstaged changes).",
            "parameters": { "type": "object", "properties": {} }
        }),
        json!({
            "name": "git_add",
            "description": "Stage files for commit.",
            "parameters": { "type": "object", "properties": { "files": { "type": "array", "items": { "type": "string" } } }, "required": ["files"] }
        }),
        json!({
            "name": "git_commit",
            "description": "Commit staged changes.",
            "parameters": { "type": "object", "properties": { "message": { "type": "string" } }, "required": ["message"] }
        }),
        json!({
            "name": "view_diff",
            "description": "View changes. Target can be 'staged', 'unstaged', or a branch/commit hash.",
            "parameters": { "type": "object", "properties": { "target": { "type": "string" } } }
        }),
        json!({
            "name": "git_log",
            "description": "View commit history.",
            "parameters": { "type": "object", "properties": { "count": { "type": "integer" } } }
        }),

        // --- Git Branching & Remote ---
        json!({
            "name": "git_checkout",
            "description": "Switch branches or create a new one.",
            "parameters": { "type": "object", "properties": { "branch": { "type": "string" }, "create_new": { "type": "boolean" } }, "required": ["branch"] }
        }),
        json!({
            "name": "git_branch_list",
            "description": "List all local branches.",
            "parameters": { "type": "object", "properties": {} }
        }),
        json!({
            "name": "git_merge",
            "description": "Merge a branch into the current one.",
            "parameters": { "type": "object", "properties": { "branch": { "type": "string" } }, "required": ["branch"] }
        }),
        json!({
            "name": "git_push",
            "description": "Push commits to remote.",
            "parameters": { "type": "object", "properties": { "remote": { "type": "string" }, "branch": { "type": "string" } }, "required": ["remote", "branch"] }
        }),
        json!({
            "name": "git_pull",
            "description": "Pull changes from remote.",
            "parameters": { "type": "object", "properties": { "remote": { "type": "string" }, "branch": { "type": "string" } }, "required": ["remote", "branch"] }
        }),

        // --- Git Safety ---
        json!({
            "name": "git_stash",
            "description": "Stash changes. Actions: 'push', 'pop', 'list'.",
            "parameters": { "type": "object", "properties": { "action": { "type": "string" } }, "required": ["action"] }
        }),
        json!({
            "name": "git_reset",
            "description": "Reset current HEAD to a state.",
            "parameters": { "type": "object", "properties": { "target": { "type": "string" }, "hard": { "type": "boolean" } }, "required": ["target"] }
        }),
        // -- RAG --
        json!({
            "name": "semantic_search",
            "description": "Search the codebase by meaning. Use this when you don't know the exact file. E.g., 'How is auth retried?'",
            "parameters": { "type": "object", "properties": { "query": { "type": "string" } }, "required": ["query"] }
        }),
    ]
}

pub fn dispatch(name: &str, args: &Value, git: &GitEngine, analysis: &AnalysisEngine) -> String {
    match name {
        // Analysis
        "get_project_structure" => {
            let depth = args["max_depth"].as_u64().unwrap_or(2) as usize;
            git.get_file_tree(depth)
        },
        "inspect_file_interface" => {
            let path = args["path"].as_str().unwrap_or("");
            analysis.get_skeleton(path)
        },
        "read_file" => {
            let path = args["path"].as_str().unwrap_or("");
            git.read_file(path)
        },
        "write_file" => {
            let path = args["path"].as_str().unwrap_or("");
            let content = args["content"].as_str().unwrap_or("");
            git.write_file(path, content)
        },

        // Git Basics
        "git_status" => git.status(),
        "git_commit" => {
            let msg = args["message"].as_str().unwrap_or("update");
            git.commit(msg)
        },
        "git_add" => {
            let files: Vec<String> = args["files"].as_array()
                .unwrap_or(&vec![])
                .iter()
                .map(|v| v.as_str().unwrap_or(".").to_string())
                .collect();
            git.add(files)
        },
        "view_diff" => {
            let target = args["target"].as_str().unwrap_or("unstaged");
            git.diff(target)
        },
        "git_log" => {
            let count = args["count"].as_u64().unwrap_or(5) as usize;
            git.log(count)
        },

        // Git Branching/Remote
        "git_checkout" => {
            let branch = args["branch"].as_str().unwrap_or("main");
            let create = args["create_new"].as_bool().unwrap_or(false);
            git.checkout(branch, create)
        },
        "git_branch_list" => git.branch_list(),
        "git_merge" => {
            let branch = args["branch"].as_str().unwrap_or("");
            git.merge(branch)
        },
        "git_push" => {
            let remote = args["remote"].as_str().unwrap_or("origin");
            let branch = args["branch"].as_str().unwrap_or("main");
            git.push(remote, branch)
        },
        "git_pull" => {
            let remote = args["remote"].as_str().unwrap_or("origin");
            let branch = args["branch"].as_str().unwrap_or("main");
            git.pull(remote, branch)
        },

        // Git Safety
        "git_stash" => {
            let action = args["action"].as_str().unwrap_or("push");
            git.stash(action)
        },
        "git_reset" => {
            let target = args["target"].as_str().unwrap_or("HEAD");
            let hard = args["hard"].as_bool().unwrap_or(false);
            git.reset(target, hard)
        },
                "semantic_search" => {
            let query = args["query"].as_str().unwrap_or("");
            indexer.search(query, 3) // Return top 3 results
        },

        _ => format!("Tool {} not found", name),

        _ => format!("Tool {} not found", name),
    }
}