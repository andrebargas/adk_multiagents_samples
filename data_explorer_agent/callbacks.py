#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

from data_explorer_agent.sub_agents.sql_explorer.tools import get_database_settings
from data_explorer_agent.utils.data_stores import get_data_store_context
from google.adk.agents.callback_context import CallbackContext


def setup_before_agent_call(callback_context: CallbackContext):
    """Setup the agent."""

    # setting up database settings in session.state
    if "database_settings" not in callback_context.state:
        db_settings = dict()
        callback_context.state["database_settings"] = db_settings
        callback_context.state["database_settings"] = get_database_settings()
    
    if "data_store_context" not in callback_context.state:
        data_store_context = dict()
        callback_context.state["data_store_context"] = get_data_store_context()

    data_store_context = callback_context.state["data_store_context"]
    schema = callback_context.state["database_settings"]["bq_ddl_schema"]

    callback_context._invocation_context.agent.instruction += (
f"""
--------- The BigQuery schema of the relevant data with a few sample rows. ---------
{schema}


--------- The Data Stores description. ---------
{data_store_context}

""")
