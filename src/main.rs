mod git;
mod analysis;
mod llm;
mod tools;

use dotenv::dotenv;
use colored::*;
use inquire::Text;
use serde_json::{json, Value};
// use std::env;

#[tokio::main]
async fn main() {
    dotenv().ok();
    
    // 1. Initialize Engines
    let git = git::GitEngine::new().expect("Failed to init git");
    let analysis = analysis::AnalysisEngine::new(git.repo_path.clone());
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
                
                // Add user message to history
                history.push(json!({ "role": "user", "parts": [{ "text": input }] }));
                print!("{}", "Thinking... ".cyan());

                // Loop for Tool execution (Agentic Loop)
                loop {
                    let response = client.chat(&history, &tools::get_tool_definitions()).await;
                    
                    match response {
                        Ok(content) => {
                            // Clean up loading spinner
                            print!("\r"); 

                            let parts = content["parts"].as_array().unwrap();
                            let first_part = &parts[0];

                            // Case A: Model wants to call a tool
                            if let Some(fc) = first_part.get("functionCall") {
                                let name = fc["name"].as_str().unwrap();
                                let args = &fc["args"];
                                
                                // println!("{} {}...", "Executing".yellow(), name);
                                
                                let result = tools::dispatch(name, args, &git, &analysis);
                                
                                // Feed result back to model
                                history.push(content.clone()); // Add the model's call
                                history.push(json!({
                                    "role": "function",
                                    "parts": [{
                                        "functionResponse": {
                                            "name": name,
                                            "response": { "result": result }
                                        }
                                    }]
                                }));
                                // Continue loop to let model interpret result
                                continue; 
                            }
                            
                            // Case B: Model returned text (Final Answer)
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