from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import OpenAI
from dotenv import load_dotenv

from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import json
import os

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI()
    # methods will go here

    async def connect_to_servers(self):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        tools=[]
        with open('mcp_servers.json', 'r') as file:
            config = json.load(file)
        for name, details in config["mcpServers"].items():
            await self.connect_to_server(details)
            server_tools = await load_mcp_tools(self.session)
            for tool in server_tools:
                tools.append(tool)
        return tools

    async def connect_to_server(self, config: dict):
        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config["env"] if config["env"] else None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
    
    async def process_query(self, query: str, available_tools) -> str:
        llm = ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"))
        agent = create_react_agent(llm, available_tools)
        result = await agent.ainvoke({"messages": query})
        return result
    
    async def chat_loop(self, query):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        try:
            response = await self.process_query(query)
            print("\n" + response)

        except Exception as e:
            print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

