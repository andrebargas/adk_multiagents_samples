#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.
import os
import json
from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
from google.cloud import logging as google_cloud_logging
from .utils.typing import Feedback
from .sub_agents import sql_explorer_agent, documents_explorer_agent, data_analysis_agent
from .sub_agents.feedback.agent import feedback_quest_agent


# Initialize Google Cloud Logging client and logger for this module
logging_client = google_cloud_logging.Client()
tool_logger = logging_client.logger("data_explorer_agent.tools")

async def call_feedback_quest_agent(
    trigger_message: str, # pylint: disable=unused-argument
    tool_context: ToolContext,
):
    """Tool to call the FeedbackQuestWorkflow agent.
    
    This tool initiates a sequence to collect and process user feedback.
    The structured feedback is stored in tool_context.state["structured_feedback_json"].
    The tool returns a final acknowledgement message for the user.
    """
    
    agent_tool = AgentTool(agent=feedback_quest_agent)

    feedback_agent_output = await agent_tool.run_async(
        args={}, tool_context=tool_context # The feedback_quest_agent itself will set "structured_feedback_json" in the state.
    )

    # Log the structured feedback, similar to the /feedback route
    if "structured_feedback_json" in tool_context.state:
        feedback_json_str = tool_context.state["structured_feedback_json"]
        if isinstance(feedback_json_str, str):
            try:
                feedback_data_dict = json.loads(feedback_json_str)
                # Validate and structure using the Feedback Pydantic model
                feedback_obj = Feedback(**feedback_data_dict)
                tool_logger.log_struct(feedback_obj.model_dump(), severity="INFO")
            except json.JSONDecodeError as e:
                tool_logger.log_struct({"error": "Failed to parse structured_feedback_json from state", "details": str(e), "raw_data": feedback_json_str}, severity="ERROR")
            except Exception as e: # Catches Pydantic validation errors and others
                tool_logger.log_struct({"error": "Failed to process structured_feedback_json for logging", "details": str(e), "raw_data": feedback_json_str}, severity="ERROR")
        else:
            tool_logger.log_struct({"error": "structured_feedback_json in state was not a string", "type": str(type(feedback_json_str)), "raw_data": str(feedback_json_str)}, severity="WARNING")

    # The structured_feedback_json is set in the state by the process_feedback sub-agent.
    return feedback_agent_output
         

async def call_db_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call sql explorer (nl2sql) agent."""

    print(os.getenv("GOOGLE_CLOUD_PROJECT"))
    agent_tool = AgentTool(agent=sql_explorer_agent)

    db_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )
    tool_context.state["sql_explorer_agent_output"] = db_agent_output
    return db_agent_output


async def call_document_explorer_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call document explorer agent."""


    agent_tool = AgentTool(agent=documents_explorer_agent)

    db_agent_output = await agent_tool.run_async(
        args={"request": question}, tool_context=tool_context
    )
    tool_context.state["documents_explorer_agent_output"] = db_agent_output
    return db_agent_output


async def call_data_analysis_agent(
    question: str,
    tool_context: ToolContext,
):
    """Tool to call data analysis (nl2py) agent."""

    if question == "N/A":
        return tool_context.state["sql_explorer_agent_output"]

    question_with_data = f"""
    Question to answer: {question}
    """

    if "query_result" in tool_context.state and tool_context.state["query_result"]:
        input_data = tool_context.state["query_result"]
        question_with_data += f"""
        Actual data to analyze prevoius quesiton is already in the following:
        {input_data} 
        """

    if "documents_explorer_agent_output" in tool_context.state and tool_context.state["documents_explorer_agent_output"]:
        documents_data = tool_context.state["documents_explorer_agent_output"]
        question_with_data += f"""
        Actual data from the documents source:
        {documents_data} 
        """

    agent_tool = AgentTool(agent=data_analysis_agent)

    ds_agent_output = await agent_tool.run_async(
        args={"request": question_with_data}, tool_context=tool_context
    )
    tool_context.state["data_analysis_agent_output"] = ds_agent_output
    return ds_agent_output
