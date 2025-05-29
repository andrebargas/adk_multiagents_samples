#  Copyright 2025 Google LLC. This software is provided as-is, without warranty
#  or representation for any use or purpose. Your use of it is subject to your
#  agreement with Google.


import os

from fastapi import FastAPI
import google.auth
from google.adk.cli.fast_api import get_fast_api_app
from dotenv import load_dotenv

from google.cloud import logging as google_cloud_logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, export

from data_explorer_agent.utils.env_vars import safe_load_env
safe_load_env(dotenv_path=".env")

from data_explorer_agent.utils.tracing import CloudTraceLoggingSpanExporter
from data_explorer_agent.utils.typing import Feedback
from data_explorer_agent.utils.utils import get_env_var, get_db_connection_string, get_env_var
from data_explorer_agent.utils.logger_config import setup_app_logger
from data_explorer_agent.utils.env_vars import safe_load_env


logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)


AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]
SERVE_WEB_INTERFACE = True

# _, project_id = google.auth.default()
project_id = get_env_var("GOOGLE_CLOUD_PROJECT", "andrebargas-sandbox")
db_connection_string = get_db_connection_string()

# Instancing Cloud Tracing
provider = TracerProvider()
processor = export.BatchSpanProcessor(CloudTraceLoggingSpanExporter(project_id=project_id))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Start FlaskAPI application
app: FastAPI = get_fast_api_app(
    agent_dir=AGENT_DIR,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
    session_db_url=db_connection_string,
)
app.title = get_env_var("AGENT_NAME", "data_explorer")
app.description = get_env_var("AGENT_DESCRIPTION", "")
app.version = get_env_var("AGENT_VERSION", "0.0.1")


# Custom routes definition
@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success", "message": "Feedback received"}, 200


# Uvincorn application execution usign main file module run
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
