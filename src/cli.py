import asyncio
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
MODEL_NAME = "gemini-2.5-flash" 
# Default to current directory if not set
TARGET_REPO = os.getenv("GIT_REPO_PATH", os.getcwd()) 
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
    repo_name = os.path.basename(os.path.abspath(TARGET_REPO))
    return HTML(
        f'<username>dev</username><at>@</at><host>gemini-cli</host>:'
        f'<path>~/{repo_name}</path><pound>$</pound> '
    )

def mcp_tool_to_gemini(tool):
    """Converts MCP JSON Schema to Gemini FunctionDeclaration."""
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=tool.inputSchema
    )

def print_help():
    """Displays a help menu using Rich tables."""
    table = Table(title="Git Agent Capabilities")

    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Examples", style="white")

    table.add_row("Navigation", "Where is the login code? | Read main.py")
    table.add_row("Status", "What did I change? | Show diff")
    table.add_row("Coding", "Create a new branch 'feature/auth' | Commit these changes")
    table.add_row("Stashing", "Stash my changes | Pop the stash | List stashes") # Added this
    table.add_row("Sync", "Push to origin | Pull latest changes")
    table.add_row("System", "exit | help")

    console.print(table)

async def run_chat_loop():
    if not GEMINI_API_KEY:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable not set.")
        return

    # 1. Configure Google GenAI Client
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # 2. Setup MCP Server Parameters
    server_params = StdioServerParameters(
        command="python",
        args=["src/server.py"], # Adjust if your server.py is elsewhere
        env={**os.environ, "GIT_REPO_PATH": TARGET_REPO}
    )

    console.print(Panel.fit(
        f"[bold green]Git Agent (Full Engineer Mode)[/bold green]\n"
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
            gemini_funcs = [mcp_tool_to_gemini(t) for t in mcp_tools.tools]
            gemini_tool = types.Tool(function_declarations=gemini_funcs)
            
            # Initialize Chat Configuration
            system_instr = (
                "You are an expert software engineer agent with full access to a git repository via tools. "
                "You can read code, search, edit files (you cannot edit file content directly, but you can manage git state), "
                "stage changes, commit, branch, and push/pull. "
                "1. Always check 'get_repo_status' first when asked about state. "
                "2. Before committing, always run 'view_diff' to verify changes. "
                "3. If asked to implement a feature, create a new branch first. "
                "4. Be concise."
            )

            config = types.GenerateContentConfig(
                tools=[gemini_tool],
                system_instruction=system_instr,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            # Start Chat Session
            chat = client.chats.create(model=MODEL_NAME, config=config)
            session = PromptSession(history=FileHistory(HISTORY_FILE), style=prompt_style)

            # 4. Main Chat Loop
            while True:
                try:
                    user_input = await session.prompt_async(get_prompt())
                    cleaned_input = user_input.strip().lower()

                    if cleaned_input in ["exit", "quit"]:
                        break
                    
                    if cleaned_input == "help":
                        print_help()
                        continue
                        
                    if not cleaned_input:
                        continue

                    with console.status("[bold cyan]Agent working...", spinner="dots"):
                        response = chat.send_message(user_input)
                        
                        while True:
                            if not response.candidates: break
                            part = response.candidates[0].content.parts[0]
                            
                            if part.function_call:
                                fn = part.function_call
                                f_name, f_args = fn.name, dict(fn.args)
                                
                                console.print(f"  [dim]>[/dim] [bold yellow]{f_name}[/bold yellow] [dim]{str(f_args)[:80]}[/dim]")

                                try:
                                    result = await mcp_session.call_tool(f_name, arguments=f_args)
                                    tool_out = result.content[0].text
                                    
                                    # Truncate visual output for user, but send full to LLM
                                    display_out = tool_out[:200] + "..." if len(tool_out) > 200 else tool_out
                                    console.print(f"  [dim]< {display_out.replace(os.linesep, ' ')}[/dim]")
                                    
                                except Exception as e:
                                    tool_out = f"Error: {str(e)}"
                                    console.print(f"  [bold red]Error:[/bold red] {e}")

                                response_part = types.Part.from_function_response(
                                    name=f_name, response={"result": tool_out}
                                )
                                response = chat.send_message([response_part])
                            else:
                                break
                    
                    console.print()
                    if response.text:
                        console.print(Markdown(response.text))
                    console.print()

                except Exception as e:
                    console.print(f"[bold red]System Error:[/bold red] {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_chat_loop())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        console.print("\n[yellow]Shutting down.[/yellow]")