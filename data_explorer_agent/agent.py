#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

import os

import google.auth
from google.adk.agents import Agent

from data_explorer_agent.prompts import return_instructions
from data_explorer_agent.callbacks import setup_before_agent_call
from data_explorer_agent.tools import call_data_analysis_agent, call_db_agent, call_document_explorer_agent
from data_explorer_agent.utils.utils import get_env_var


root_agent = Agent(
    name="root_agent",
    model=get_env_var("ROOT_AGENT_MODEL", "gemini-2.0-flash-001"),
    instruction=return_instructions(),
    before_agent_callback=setup_before_agent_call,
    tools=[
           call_data_analysis_agent, 
           call_db_agent, 
           call_document_explorer_agent],
)
