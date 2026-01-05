mod git;
mod analysis;
mod llm;
mod tools;
mod chunker; // New
mod indexer; // New

use dotenv::dotenv;
use colored::*;
use inquire::Text;
use serde_json::{json, Value};

#[tokio::main]
async fn main() {
    dotenv().ok();
    
    // 1. Initialize Engines
    let git = git::GitEngine::new().expect("Failed to init git");
    let analysis = analysis::AnalysisEngine::new(git.repo_path.clone());
    
    // Initialize RAG Indexer
    // This will download the model (if new) and index the repo (on startup)
    let mut indexer = indexer::SemanticIndexer::new(git.repo_path.clone());
    indexer.index_repo(&git); 

    let client = llm::GeminiClient::new();

    println!("{}", format!("Git Agent (Rust) active in: {:?}", git.repo_path).green().bold());

    // 2. Chat History
    let mut history: Vec<Value> = Vec::new();

    // 3. Main Loop
    loop {
        let user_input = Text::new("dev@agent$").prompt();
        match user_input {
            Ok(input) => {
                if input == "exit" { break; }
                
                // Re-index on specific command or occasionally (optional optimization)
                if input == "reindex" {
                    indexer.index_repo(&git);
                    continue;
                }

                history.push(json!({ "role": "user", "parts": [{ "text": input }] }));
                print!("{}", "Thinking... ".cyan());

                loop {
                    // Pass indexer to dispatch
                    let response = client.chat(&history, &tools::get_tool_definitions()).await;
                    
                    match response {
                        Ok(content) => {
                            print!("\r"); 

                            let parts = content["parts"].as_array().unwrap();
                            let first_part = &parts[0];

                            if let Some(fc) = first_part.get("functionCall") {
                                let name = fc["name"].as_str().unwrap();
                                let args = &fc["args"];
                                
                                println!("{} {}...", "Executing".yellow(), name);
                                
                                // Pass indexer reference
                                let result = tools::dispatch(name, args, &git, &analysis, &indexer);
                                
                                history.push(content.clone());
                                history.push(json!({
                                    "role": "function",
                                    "parts": [{
                                        "functionResponse": {
                                            "name": name,
                                            "response": { "result": result }
                                        }
                                    }]
                                }));
                                continue; 
                            }
                            
                            if let Some(text) = first_part.get("text") {
                                println!("\n{}", text.as_str().unwrap());
                                history.push(content.clone());
                                break;
                            }
                        },
                        Err(e) => {
                            println!("{}", format!("Error: {}", e).red());
                            break;
                        }
                    }
                }
            },
            Err(_) => break,
        }
    }
}