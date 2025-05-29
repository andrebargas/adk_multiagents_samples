source "$(pwd)/deployment/scripts/utils.sh"

# --- Configuration ---
ENV_FILE=".env"
PYTHON_SCRIPT_NAME="env_to_yaml.py" # Name of your Python conversion script
GENERATED_YAML_NAME=".cloud_run_env_vars.yaml"

PYTHON_SCRIPT_PATH="$(pwd)/deployment/scripts/${PYTHON_SCRIPT_NAME}"
ENV_FILE_PATH="$(pwd)/${ENV_FILE}"
GENERATED_YAML_PATH="$(pwd)/${GENERATED_YAML_NAME}"

# --- Check .env file and transform to .yaml (Enables --env-vars-file flag)---
if [ -f "${ENV_FILE_PATH}" ]; then
    log "Sourcing environment variables from ${ENV_FILE_PATH} for script execution..."
    # shellcheck source=/dev/null
    source "${ENV_FILE_PATH}"

    log "Generating YAML file from ${ENV_FILE_PATH} for Cloud Run environment variables..."
    PYTHON_CMD=python3
    if ! command -v python3 &> /dev/null; then
        log "python3 command not found, trying python..."
        PYTHON_CMD=python
        if ! command -v python &> /dev/null; then
            error_exit "Error: Neither python3 nor python command found. Please install Python."
        fi
    fi

    if ${PYTHON_CMD} "${PYTHON_SCRIPT_PATH}" "${ENV_FILE_PATH}" "${GENERATED_YAML_PATH}"; then
        log "Successfully generated ${GENERATED_YAML_PATH}"
    else
        error_exit "Error: Failed to generate YAML file from ${ENV_FILE_PATH} using ${PYTHON_SCRIPT_PATH}."
    fi
else
    error_exit "Deployment FAILED. Environment file ${ENV_FILE_PATH} not found." 
fi

log "Deploying service '${SERVICE_NAME}' to Cloud Run project '${CLOUD_RUN_PROJECT}' in region '${CLOUD_RUN_LOCATION}'..."
CLOUD_SQL_CONNECTION_NAME="${DB_PROJECT_ID}:${DB_REGION}:${DB_INSTANCE_NAME}"

# Deploy the service to Cloud Run
if gcloud run deploy $SERVICE_NAME \
		--source . \
		--memory "4Gi" \
		--project $CLOUD_RUN_PROJECT \
		--region $CLOUD_RUN_LOCATION \
		--no-allow-unauthenticated \
        --add-cloudsql-instances $CLOUD_SQL_CONNECTION_NAME \
		--env-vars-file $GENERATED_YAML_PATH; then
    log "Service '${SERVICE_NAME}' deployed successfully."
else
    error_exit "Deployment FAILED. Failed to deploy service '${SERVICE_NAME}'"
fi

# Cleanup: Remove the generated YAML file if it exists
if [ -f "${GENERATED_YAML_PATH}" ]; then
    echo "Cleaning up ${GENERATED_YAML_PATH}..."
    rm -f "${GENERATED_YAML_PATH}"
fi
echo "Cloud Run deployment script finished successfully."
