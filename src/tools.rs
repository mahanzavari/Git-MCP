use serde_json::{json, Value};
use crate::git::GitEngine;
use crate::analysis::AnalysisEngine;

pub fn get_tool_definitions() -> Vec<Value> {
    vec![
        json!({
            "name": "get_project_structure",
            "description": "See the folder layout.",
            "parameters": { "type": "object", "properties": { "max_depth": { "type": "integer" } } }
        }),
        json!({
            "name": "inspect_file_interface",
            "description": "See code skeleton (classes/funcs) without reading body.",
            "parameters": { "type": "object", "properties": { "path": { "type": "string" } }, "required": ["path"] }
        }),
        json!({
            "name": "read_file",
            "description": "Read file content.",
            "parameters": { "type": "object", "properties": { "path": { "type": "string" } }, "required": ["path"] }
        }),
        json!({
            "name": "git_status",
            "description": "Check git status.",
            "parameters": { "type": "object", "properties": {} }
        }),
        json!({
            "name": "git_commit",
            "description": "Commit changes.",
            "parameters": { "type": "object", "properties": { "message": { "type": "string" } }, "required": ["message"] }
        }),
    ]
}

pub fn dispatch(name: &str, args: &Value, git: &GitEngine, analysis: &AnalysisEngine) -> String {
    match name {
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
        "git_status" => git.status(),
        "git_commit" => {
            let msg = args["message"].as_str().unwrap_or("update");
            git.commit(msg)
        },
        _ => format!("Tool {} not found", name),
    }
}