import asyncio
import os
import sys
import json

# UI Libraries
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# AI & MCP Libraries
import google.generativeai as genai
from google.protobuf import struct_pb2
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
MODEL_NAME = "gemini-3.0-flash" 
TARGET_REPO = os.getenv("GIT_REPO_PATH", "/home/mahan/Projects/git-mcp") 
HISTORY_FILE = ".git_agent_history"

console = Console()

# Ubuntu-style Prompt Colors
prompt_style = Style.from_dict({
    'username': '#87af5f bold',   # Green
    'at':       '#ffffff',        # White
    'host':     '#5f87af bold',   # Blue
    'path':     '#d75f5f',        # Red
    'pound':    '#ffffff bold',
})

def get_prompt():
    """Builds a PS1-style prompt: user@git-agent:~/repo$"""
    repo_name = os.path.basename(TARGET_REPO)
    return HTML(
        f'<username>user</username><at>@</at><host>gemini-cli</host>:'
        f'<path>~/{repo_name}</path><pound>$</pound> '
    )

def mcp_tool_to_gemini(tool):
    """
    Converts MCP JSON Schema to Gemini Tool declaration.
    """
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.inputSchema
    }

async def run_chat_loop():
    if not GOOGLE_API_KEY:
        console.print("[bold red]Error:[/bold red] GOOGLE_API_KEY environment variable not set.")
        console.print("Get one here: https://aistudio.google.com/app/apikey")
        return

    # 1. Configure Google GenAI
    genai.configure(api_key=GOOGLE_API_KEY)
    
    # 2. Setup MCP Server Parameters
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"], # Assumes server.py is in the same folder
        env={**os.environ, "GIT_REPO_PATH": TARGET_REPO}
    )

    console.print(Panel.fit(
        f"[bold green]Git Agent (Gemini Edition)[/bold green]\n"
        f"[dim]Repo: {TARGET_REPO}[/dim]\n"
        f"[dim]Model: {MODEL_NAME}[/dim]",
        border_style="green"
    ))

    # 3. Connect to MCP Server
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()
            
            # Load Tools from Server
            mcp_tools = await mcp_session.list_tools()
            
            # Convert to Google Format
            gemini_tools = [mcp_tool_to_gemini(t) for t in mcp_tools.tools]
            
            # Initialize Model
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                tools=gemini_tools,
                system_instruction="You are a senior developer assistant. You have access to a git repository. Always SEARCH for code before reading files. Be concise."
            )

            # Start Chat Session (Handles history automatically)
            chat = model.start_chat(enable_automatic_function_calling=False)
            
            # Setup Shell Input (Prompt Toolkit)
            session = PromptSession(history=FileHistory(HISTORY_FILE), style=prompt_style)

            # 4. Main Chat Loop
            while True:
                try:
                    # Get input (with history up/down support)
                    user_input = await session.prompt_async(get_prompt())
                    
                    if user_input.strip().lower() in ["exit", "quit"]:
                        break
                    if not user_input.strip():
                        continue

                    # --- Interaction Loop ---
                    with console.status("[bold cyan]Gemini is thinking...", spinner="dots"):
                        # Send initial message
                        response = chat.send_message(user_input)
                        
                        # Handle Tool Execution Loop
                        while True:
                            part = response.parts[0] 
                            
                            # Check if the model wants to call a function
                            if fn_call := part.function_call:
                                func_name = fn_call.name
                                func_args = dict(fn_call.args)
                                
                                console.print(f"  [dim]Executing:[/dim] [bold yellow]{func_name}[/bold yellow] [dim]{str(func_args)[:60]}...[/dim]")

                                # Execute Tool via MCP
                                try:
                                    result = await mcp_session.call_tool(func_name, arguments=func_args)
                                    tool_output = result.content[0].text
                                except Exception as e:
                                    tool_output = f"Error: {str(e)}"
                                    console.print(f"  [bold red]Tool Error:[/bold red] {e}")

                                # Send Result Back to Gemini
                                # Gemini expects a strictly formatted function_response
                                response = chat.send_message(
                                    {
                                        "parts": [
                                            {
                                                "function_response": {
                                                    "name": func_name,
                                                    "response": {"result": tool_output}
                                                }
                                            }
                                        ]
                                    }
                                )
                            else:
                                # No function call -> Final text response
                                break
                    
                    # Print Final Answer
                    console.print()
                    console.print(Markdown(response.text))
                    console.print()

                except Exception as e:
                    console.print(f"[bold red]System Error:[/bold red] {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_chat_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")