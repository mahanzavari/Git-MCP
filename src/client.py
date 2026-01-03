import asyncio
import os
import json
import sys
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

API_BASE = "https://api.gpt4-all.xyz/v1"
API_KEY = os.getenv("OPENAI_API_KEY", "g4a-iya0hKq8xWuFHj6z_gzCSK7no30MKGPns_g9KhpDk9I")
MODEL_NAME = "gemini-3-flash-preview" 
TARGET_REPO = "/home/mahan/Projects/git-mcp"
# ------------------------------------------------------------------

# Initialize OpenAI Client with your Custom URL
client = AsyncOpenAI(
    base_url=API_BASE,
    api_key=API_KEY
)

async def run_chat_loop():
    # 1. Configure the MCP Server process
    server_params = StdioServerParameters(
        command="python", # Ensure 'python' is in your PATH
        args=["server.py"], # This is the file we created previously
        env={
            **os.environ, 
            "GIT_REPO_PATH": TARGET_REPO # Pass the repo path to the server
        }
    )

    print(f"🔌 Connecting to Git MCP Server for repo: {TARGET_REPO}...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 2. Initialize the MCP Protocol
            await session.initialize()
            
            # 3. List available tools from our Git Server
            mcp_tools = await session.list_tools()
            
            # 4. Convert MCP tools to OpenAI Tool Format
            openai_tools = [{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            } for tool in mcp_tools.tools]

            print(f"✅ Loaded {len(openai_tools)} tools from Git Server.")
            print("💬 Enter your prompt (or 'quit' to exit):")

            # 5. Start the Chat Loop
            messages = [
                {"role": "system", "content": "You are a helpful Git Assistant. You have access to a repository via tools. Always Search before reading files. Don't read whole files if they are huge."}
            ]

            while True:
                user_input = input("\n> ")
                if user_input.lower() in ["quit", "exit"]:
                    break

                messages.append({"role": "user", "content": user_input})

                # --- The Reasoning Loop ---
                while True:
                    # A. Call LLM
                    try:
                        response = await client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=messages,
                            tools=openai_tools,
                            tool_choice="auto"
                        )
                    except Exception as e:
                        print(f"❌ API Error: {e}")
                        break

                    assistant_msg = response.choices[0].message
                    messages.append(assistant_msg)

                    # B. Check if LLM wants to run a tool
                    if assistant_msg.tool_calls:
                        print("  🛠️  Agent is thinking/using tools...")
                        
                        for tool_call in assistant_msg.tool_calls:
                            func_name = tool_call.function.name
                            func_args = json.loads(tool_call.function.arguments)
                            
                            print(f"  👉 Executing: {func_name}({func_args})")
                            
                            # C. Execute the tool on the MCP Server
                            try:
                                result = await session.call_tool(func_name, arguments=func_args)
                                
                                # MCP returns a list of content, we usually just want the text
                                tool_output = result.content[0].text
                            except Exception as e:
                                tool_output = f"Error executing tool: {str(e)}"

                            # D. Feed result back to LLM
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_output
                            })
                    else:
                        # No more tools needed, print final answer
                        print(f"\n🤖 {assistant_msg.content}")
                        break

if __name__ == "__main__":
    try:
        asyncio.run(run_chat_loop())
    except KeyboardInterrupt:
        print("\nGoodbye!")