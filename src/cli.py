import asyncio
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# UI Libraries
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# AI & MCP Libraries
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
MODEL_NAME = "gemini-2.5-flash" 
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
    Converts MCP JSON Schema to Gemini FunctionDeclaration.
    """
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=tool.inputSchema
    )

async def run_chat_loop():
    if not GEMINI_API_KEY:
        console.print("[bold red]Error:[/bold red] GOOGLE_API_KEY environment variable not set.")
        console.print("Get one here: https://aistudio.google.com/app/apikey")
        return

    # 1. Configure Google GenAI Client
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 2. Setup MCP Server Parameters
    server_params = StdioServerParameters(
        command="python",
        args=["src/server.py"], # Ensure this points to your server file
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
            # Note: types.Tool takes a list of function_declarations
            gemini_funcs = [mcp_tool_to_gemini(t) for t in mcp_tools.tools]
            gemini_tool = types.Tool(function_declarations=gemini_funcs)
            
            # Initialize Chat Configuration
            config = types.GenerateContentConfig(
                tools=[gemini_tool],
                system_instruction="You are a senior developer assistant. You have access to a git repository. Always SEARCH for code before reading files. Be concise.",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            # Start Chat Session
            chat = client.chats.create(model=MODEL_NAME, config=config)
            
            # Setup Shell Input
            session = PromptSession(history=FileHistory(HISTORY_FILE), style=prompt_style)

            # 4. Main Chat Loop
            while True:
                try:
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
                            # Gemini response structure: candidates -> content -> parts
                            if not response.candidates:
                                break
                                
                            part = response.candidates[0].content.parts[0]
                            
                            # Check for function call
                            if part.function_call:
                                fn_call = part.function_call
                                func_name = fn_call.name
                                func_args = fn_call.args
                                
                                console.print(f"  [dim]Executing:[/dim] [bold yellow]{func_name}[/bold yellow] [dim]{str(func_args)[:60]}...[/dim]")

                                # Execute Tool via MCP
                                try:
                                    # Convert args to dict if they aren't already
                                    args_dict = dict(func_args) if func_args else {}
                                    result = await mcp_session.call_tool(func_name, arguments=args_dict)
                                    tool_output = result.content[0].text
                                except Exception as e:
                                    tool_output = f"Error: {str(e)}"
                                    console.print(f"  [bold red]Tool Error:[/bold red] {e}")

                                # Send Result Back to Gemini
                                # The new SDK uses 'types.Part.from_function_response'
                                response_part = types.Part.from_function_response(
                                    name=func_name,
                                    response={"result": tool_output}
                                )
                                
                                response = chat.send_message([response_part])
                            else:
                                # No function call -> Final text response
                                break
                    
                    # Print Final Answer
                    console.print()
                    if response.text:
                        console.print(Markdown(response.text))
                    else:
                        console.print("[dim]No text response.[/dim]")
                    console.print()

                except Exception as e:
                    console.print(f"[bold red]System Error:[/bold red] {e}")
                    # Uncomment for debugging:
                    # import traceback; traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(run_chat_loop())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")