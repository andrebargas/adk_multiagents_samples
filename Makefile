# Configuration
ENV_FILE := .env
CLOUD_SQL_PROXY_BINARY := ./cloud-sql-proxy
# User specified darwin.arm64. Consider making this configurable if needed for other platforms.
CLOUD_SQL_PROXY_URL := https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.16.0/cloud-sql-proxy.darwin.arm64
CLOUD_SQL_PROXY_PORT := 5433

# Load environment variables from .env file if it exists
-include $(ENV_FILE)

install:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "uv is not installed. Installing uv..."; \
		curl -LsSf https://astral.sh/uv/0.6.12/install.sh | sh; \
		echo "UV has been installed. If 'uv sync' below fails, you might need to open a new terminal or source your shell profile (e.g., 'source ~/.bashrc' or 'source ~/.zshrc') and try again."; \
	else \
		echo "uv is already installed."; \
	fi
	uv sync --dev --extra jupyter --frozen

	@echo "Checking for cloud-sql-proxy..."
	@if [ -f "${CLOUD_SQL_PROXY_BINARY}" ] && [ -x "${CLOUD_SQL_PROXY_BINARY}" ]; then \
		echo "cloud-sql-proxy already exists and is executable at $@."; \
	else \
		echo "Downloading cloud-sql-proxy to $@ from $(CLOUD_SQL_PROXY_URL)..."; \
		curl -o "${CLOUD_SQL_PROXY_BINARY}" "${CLOUD_SQL_PROXY_URL}"; \
		chmod +x "${CLOUD_SQL_PROXY_BINARY}"; \
		echo "cloud-sql-proxy downloaded and made executable at "${CLOUD_SQL_PROXY_BINARY}"."; \
	fi

test:
	uv run pytest tests/unit && uv run pytest tests/integration

run-adk-dev: install
	@echo "Attempting to start cloud-sql-proxy for playground..."
	$(CLOUD_SQL_PROXY_BINARY) "$(DB_PROJECT_ID)":"$(DB_REGION)":"$(DB_INSTANCE_NAME)" --port="$(CLOUD_SQL_PROXY_PORT)" & export PROXY_PID=$$!; \
	echo "Cloud SQL Proxy connecting to $(DB_PROJECT_ID):$(DB_REGION):$(DB_INSTANCE_ID) on port $(CLOUD_SQL_PROXY_PORT) with PID $$PROXY_PID."; \
	trap 'echo "Stopping cloud-sql-proxy (PID $$PROXY_PID)..."; kill $$PROXY_PID 2>/dev/null || true; echo "Proxy stopped."' EXIT INT TERM; \
	uv run adk web --port 8501 --session_db_url postgresql+psycopg2://"${DB_USER}":"${DB_PASSWORD}"@127.0.0.1:5433/"${DB_SESSIONS_NAME}"

run-dev: install
	@echo "Attempting to start cloud-sql-proxy for local-backend..."
	$(CLOUD_SQL_PROXY_BINARY) $(DB_PROJECT_ID):$(DB_REGION):$(DB_INSTANCE_NAME) --port=$(CLOUD_SQL_PROXY_PORT) & \
	PROXY_PID=$$!; \
	echo "Cloud SQL Proxy connecting to $(DB_PROJECT_ID):$(DB_REGION):$(DB_INSTANCE_NAME) on port $(CLOUD_SQL_PROXY_PORT) with PID $$PROXY_PID."; \
	trap 'echo "Stopping cloud-sql-proxy (PID $$PROXY_PID)..."; kill $$PROXY_PID 2>/dev/null || true; echo "Proxy stopped."' EXIT INT TERM; \
	uv run uvicorn data_explorer_agent.server:app --host 0.0.0.0 --port 8080

deploy-dev:
	# Export dependencies to requirements file using uv export.
	uv export --no-hashes --no-sources --no-header --no-dev --no-emit-project > requirements.txt && bash deployment/scripts/deploy_cloudrun.sh

setup-dev-env:
	PROJECT_ID=$$(gcloud config get-value project) && \
	(cd deployment/terraform/dev && terraform init && \ 
	terraform apply --var-file vars/env.tfvars --auto-approve)

lint:
	uv run codespell
	uv run ruff check . --diff
	uv run ruff format . --check --diff
	uv run mypy .

clean-proxy:
	@if [ -f "$(CLOUD_SQL_PROXY_BINARY)" ]; then \
		echo "Removing $(CLOUD_SQL_PROXY_BINARY)..."; \
		rm -f $(CLOUD_SQL_PROXY_BINARY); \
	else \
		echo "$(CLOUD_SQL_PROXY_BINARY) not found."; \
	fi
