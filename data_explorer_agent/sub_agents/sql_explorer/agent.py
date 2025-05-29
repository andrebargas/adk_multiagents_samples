#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext

from data_explorer_agent.sub_agents.sql_explorer.prompts import return_instructions
from data_explorer_agent.sub_agents.sql_explorer import tools
from data_explorer_agent.sub_agents.sql_explorer.tools import get_database_settings
from data_explorer_agent.utils.utils import get_env_var


def setup_before_agent_call(callback_context: CallbackContext) -> None:
    """Setup the agent."""

    if "database_settings" not in callback_context.state:
        callback_context.state["database_settings"] = get_database_settings()


sql_explorer_agent = Agent(
    model=get_env_var("SQL_EXPLORER_AGENT_MODEL", "gemini-2.0-flash-001"),
    name="sql_explorer_agent",
    instruction=return_instructions(),
    tools=[
        tools.initial_bq_nl2sql,
        tools.run_bigquery_validation,
    ],
    before_agent_callback=setup_before_agent_call,
)
