#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.

from google.adk.agents import Agent
from google.adk.code_executors import VertexAiCodeExecutor

from data_explorer_agent.sub_agents.data_analysis.prompts import return_instructions
from data_explorer_agent.utils.utils import get_env_var
from data_explorer_agent.utils.extentions_utils import get_or_create_code_interpreter

code_interpreter_name = get_env_var('CODE_INTERPRETER_EXTENSION_NAME', get_or_create_code_interpreter())


data_analysis_agent = Agent(
    model=get_env_var("DATA_ANALYSIS_AGENT_MODEL", "gemini-2.0-flash-001"),
    name="data_analysis_agent",
    instruction=return_instructions(),
    code_executor=VertexAiCodeExecutor(
        resource_name=code_interpreter_name, 
        optimize_data_file=True,
        stateful=True,
    ),
)
