import os
import logging
from dotenv import dotenv_values
from data_explorer_agent.utils.utils import get_env_var

logger = logging.getLogger(f"{get_env_var('DEFAULT_LOGGER_NAME', 'data_explorer_app')}.{__name__}")

ALLOWED_VARS = [
    "CLOUD_RUN_PROJECT",
    "CLOUD_RUN_LOCATION",
    "AGENT_PATH",
    "SERVICE_NAME",
    "APP_NAME",
    "AGENT_NAME",
    "AGENT_DESCRIPTION",
    "AGENT_VERSION",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "NL2SQL_METHOD",
    "BQ_PROJECT_ID",
    "BQ_DATASET_ID",
    "ROOT_AGENT_MODEL",
    "DATA_ANALYSIS_AGENT_MODEL",
    "DOCUMENTS_EXPLORER_AGENT_MODEL",
    "SQL_EXPLORER_AGENT_MODEL",
    "BASELINE_NL2SQL_MODEL",
    "GITLAB_EXPLORER_AGENT_MODEL",
    "SEARCH_ENGINE_ID",
    "RAG_CORPUS_ID",
    "DB_PROJECT_ID",
    "DB_REGION",
    "DB_INSTANCE_NAME",
    "DB_SESSIONS_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "ATF_REPO_NAME"
]


def safe_load_env(dotenv_path: str = '.env', allowed_variables: list = ALLOWED_VARS):
    """
    Safely loads environment variables from a .env file.
    """
    
    if allowed_variables is None:
        allowed_variables = []

    from dotenv import dotenv_values
    env_vars_from_file = dotenv_values(dotenv_path)

    loaded_env_vars = {}
    missing_variables = []

    if not env_vars_from_file:
        logger.warning(f"No variables found in '{dotenv_path}'.")
        return {}

    for key, value in env_vars_from_file.items():
        if allowed_variables and key not in allowed_variables:
            logger.warning(f"Variable '{key}' found in '{dotenv_path}'.")
            # continue # Uncomment if dont want to add the var outside the allow list
            pass

        # Strip quotes from the value
        if isinstance(value, str):
            if (value.startswith("'") and value.endswith("'")) or \
               (value.startswith('"') and value.endswith('"')):
                processed_value = value[1:-1]
            else:
                processed_value = value
        else:
            processed_value = value

        os.environ[key] = processed_value
        loaded_env_vars[key] = processed_value

    # Check for missing allowed variables
    for var_name in allowed_variables:
        if var_name not in loaded_env_vars:
            missing_variables.append(var_name)

    if missing_variables:
        logger.warning(f"The following allowed variables are missing from '{dotenv_path}': {', '.join(missing_variables)}")

    logger.info(get_env_var("GOOGLE_CLOUD_PROJECT"))
    return loaded_env_vars