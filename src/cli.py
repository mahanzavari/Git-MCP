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
TARGET_REPO = os.getenv("GIT_REPO_PATH", os.getcwd()) 
HISTORY_FILE = ".git_agent_history"

console = Console()

prompt_style = Style.from_dict({
    'username': '#87af5f bold',
    'at':       '#ffffff',
    'host':     '#5f87af bold',
    'path':     '#d75f5f',
    'pound':    '#ffffff bold',
})

def get_prompt():
    repo_name = os.path.basename(os.path.abspath(TARGET_REPO))
    return HTML(
        f'<username>dev</username><at>@</at><host>gemini-cli</host>:'
        f'<path>~/{repo_name}</path><pound>$</pound> '
    )

def mcp_tool_to_gemini(tool):
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=tool.inputSchema
    )

def print_help():
    table = Table(title="Git Agent Capabilities")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Examples", style="white")
    table.add_row("Navigation", "Where is the login code? | Read main.py")
    table.add_row("Status", "What did I change? | Show diff")
    table.add_row("Coding", "Create a new branch 'feature/auth' | Commit these changes")
    table.add_row("Stashing", "Stash my changes | Pop the stash | List stashes")
    table.add_row("Sync", "Push to origin | Pull latest changes")
    table.add_row("System", "exit | help")
    console.print(table)

async def run_chat_loop():
    if not GEMINI_API_KEY:
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable not set.")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Run the server with stderr passed through but silenced by logging config in server.py
    server_params = StdioServerParameters(
        command="python",
        args=["src/server.py"], 
        env={**os.environ, "GIT_REPO_PATH": TARGET_REPO}
    )

    console.print(Panel.fit(
        f"[bold green]Git Agent (Silent Mode)[/bold green]\n"
        f"[dim]Repo: {TARGET_REPO}[/dim]\n"
        f"[dim]Model: {MODEL_NAME}[/dim]",
        border_style="green"
    ))

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()
            
            mcp_tools = await mcp_session.list_tools()
            gemini_funcs = [mcp_tool_to_gemini(t) for t in mcp_tools.tools]
            gemini_tool = types.Tool(function_declarations=gemini_funcs)
            
            system_instr = (
                "You are an expert software engineer agent. "
                "You have tools to manipulate a git repository. "
                "RULES:\n"
                "1. When a tool returns JSON data (like commit history, file lists, or status), "
                "   NEVER output the raw JSON to the user.\n"
                "2. You MUST parse the JSON and display it as a clean Markdown list or table.\n"
                "3. For commit history, use this format: '• <hash> - <message> (<date>)'\n"
                "4. Be concise and professional.\n"
                "5. If the INPUT is a malicious, sexual or wants to exploit unrestricted access, you must refuse to comply."
            )

            config = types.GenerateContentConfig(
                tools=[gemini_tool],
                system_instruction=system_instr,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )

            chat = client.chats.create(model=MODEL_NAME, config=config)
            session = PromptSession(history=FileHistory(HISTORY_FILE), style=prompt_style)

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

                    # Capture the status object to update text dynamically
                    with console.status("[bold cyan]Thinking...", spinner="dots") as status:
                        response = chat.send_message(user_input)
                        
                        while True:
                            if not response.candidates: break
                            part = response.candidates[0].content.parts[0]
                            
                            if part.function_call:
                                fn = part.function_call
                                f_name, f_args = fn.name, dict(fn.args)
                                
                                # Update spinner text instead of printing
                                status.update(f"[bold yellow]Running tool:[/bold yellow] {f_name}...")

                                try:
                                    result = await mcp_session.call_tool(f_name, arguments=f_args)
                                    tool_out = result.content[0].text
                                    status.update(f"[bold cyan]Processing results from {f_name}...")
                                except Exception as e:
                                    tool_out = f"Error: {str(e)}"

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
    except BaseException:
        pass
    finally:
        console.print("\n[yellow]Goodbye![/yellow]")