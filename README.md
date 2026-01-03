# 📦 Git MCP Agent

A specialized AI Agent that connects Google's **Gemini 2.0 Flash** to your local **Git repositories**. It allows you to chat with your codebase securely, perform semantic searches, and analyze commit history without hallucinating file paths.

## ✨ Features
*   **Context-Aware:** Reads only relevant file segments to save tokens.
*   **Live State:** Can see uncommitted changes (dirty state) in your working directory.
*   **Safe:** Read-only access. Cannot push, commit, or delete files.
*   **CLI Interface:** Ubuntu-style terminal with history and syntax highlighting.

## 🛠️ Installation

1.  **Prerequisites**
    *   Python 3.10 or higher
    *   A Google AI Studio API Key (Free)

2.  **Setup**
    ```bash
    git clone https://github.com/mahanzavari/Git-MCP
    cd git-mcp
    # Create virtual env (Recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

    # Install dependencies
    pip install -r requirements.txt
    ```
    *(Note: Ensure `requirements.txt` includes: `google-genai`, `mcp`, `prompt_toolkit`, `rich`, `python-dotenv`)*

3.  **Configuration**
    Create a `.env` file or export variables:
    ```bash
    export GOOGLE_API_KEY="AIzaSy..."
    export GIT_REPO_PATH="/path/to/your/target/repo"
    ```

## 🚀 Usage

Run the CLI interface:
```bash
python src/cli.py
```

## 💡 Example Queries
*   *"What is the status of the repo?"*
*   *"Search for where 'API_BASE' is defined."*
*   *"Explain the changes in the last commit."*
*   *"Look at my uncommitted changes in cli.py and tell me if I introduced a bug."*
