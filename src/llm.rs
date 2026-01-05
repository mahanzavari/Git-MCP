use serde_json::{json, Value};
use std::env;

pub struct GeminiClient {
    api_key: String,
    model: String,
    client: reqwest::Client,
}

impl GeminiClient {
    pub fn new() -> Self {
        Self {
            api_key: env::var("GEMINI_API_KEY").expect("GEMINI_API_KEY must be set"),
            model: "gemini-2.5-flash".to_string(),
            client: reqwest::Client::new(),
        }
    }

    pub async fn chat(&self, history: &Vec<Value>, tools: &Vec<Value>) -> Result<Value, String> {
        let url = format!(
            "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
            self.model, self.api_key
        );

        let system_instr = json!({
            "parts": [{ "text": "You are a Senior Software Engineer Agent. 
            Use the Map->Index->Zoom strategy. 
            1. get_project_structure
            2. inspect_file_interface
            3. read_file (only if needed)
            NEVER output raw JSON. Use Markdown tables/lists." }]
        });

        let body = json!({
            "contents": history,
            "tools": [{ "function_declarations": tools }],
            "system_instruction": system_instr
        });

        let res = self.client.post(&url).json(&body).send().await
            .map_err(|e| e.to_string())?;

        let json_res: Value = res.json().await.map_err(|e| e.to_string())?;
        
        // Extract the candidate
        if let Some(candidate) = json_res["candidates"][0]["content"].as_object() {
            Ok(json!(candidate))
        } else {
            Err(format!("API Error: {:?}", json_res))
        }
    }
}