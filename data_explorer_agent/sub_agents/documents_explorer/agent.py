#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

from google.adk.agents import Agent

from data_explorer_agent.sub_agents.documents_explorer.prompts import return_instructions
from data_explorer_agent.sub_agents.documents_explorer.tools import get_rag_engine_tool, get_vertex_search_tool
from data_explorer_agent.utils.utils import get_env_var



documents_explorer_agent = Agent(
    model=get_env_var("DOCUMENTS_EXPLORER_AGENT_MODEL", "gemini-2.0-flash-001"),
    name="documents_explorer_agent",
    instruction=return_instructions(),
    tools=[ 
        get_rag_engine_tool(),
        # get_vertex_search_tool()
    ],
    # before_agent_callback=setup_before_agent_call,
)
