# specialist_agent_jwt.py

import flask
import threading
import uuid
import time
import json
from queue import Queue, Empty
import logging
import datetime
import jwt # PyJWT
from functools import wraps

# --- Langchain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import TavilySearchResults

# --- Agent Configuration & State ---
AGENT_ID = "specialist-genai-jwt-001"
AGENT_NAME = "JWTExtractSpecialist_AIStudioKey"
AGENT_DESCRIPTION = "Specialist with JWT Auth for browse & extract."
BASE_URL = "http://localhost:5001"
PORT = 5001
SECRET_KEY = "a4823hfndsn83ndno3287bd" # IMPORTANT: Use a strong, unique key, ideally from env var

# --- API Keys (HARDCODED - Consider environment variables for production) ---
TAVILY_API_KEY = "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"
GOOGLE_AI_STUDIO_API_KEY = "AIzaSyCW0SFlsOvlQLYm2__ROSrFNH0V1wPnr9k"
GEMINI_MODEL_FOR_STUDIO = "gemini-2.0-flash"


TASKS = {}
UPDATE_QUEUES = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(AGENT_NAME)
app = flask.Flask(AGENT_NAME)
app.config["SECRET_KEY"] = SECRET_KEY

AGENT_CARD = {
  "id": AGENT_ID, "name": AGENT_NAME, "description": AGENT_DESCRIPTION, "url": BASE_URL,
  "endpoints": {
    "agent_card": "/.well-known/agent.json",
    "login": "/login", # New login endpoint
    "submit_task": "/submit_task",
    "task_updates": "/task_updates/{task_id}"
  },
  "capabilities": {
      "async": True,
      "streaming_updates": "sse",
      "auth_required": True, # Authentication is now required
      "auth_info": {
          "type": "Bearer",
          "token_location": "AuthorizationHeader",
          "endpoints_requiring_auth": ["/submit_task", "/task_updates/{task_id}"],
          "login_endpoint": "/login"
      }
  },
  "skills": [{
      "id": "browse_extract", "name": "Browse and Extract (AI Studio, JWT)",
      "description": "Uses Tavily and Gemini (Google AI Studio key) for extraction, protected by JWT.",
      "input_description": "{'search_topic': 'string', 'extraction_instruction': 'string'}",
      "output_artefact_description": "{'extracted_data': 'string', 'source_query': 'string', 'search_results_summary': 'object_or_string'}"
  }]
}

# --- JWT Authentication Decorator ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in flask.request.headers:
            auth_header = flask.request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return flask.jsonify({"message": "Bearer token malformed."}), 401

        if not token:
            return flask.jsonify({"message": "Token is missing!"}), 401

        try:
            # In a real app, you'd store user data from the token, e.g., in flask.g
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data.get('user_id', 'unknown_user_from_token') # Example claim
            logger.info(f"Token validated for user: {current_user}")
        except jwt.ExpiredSignatureError:
            return flask.jsonify({"message": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return flask.jsonify({"message": "Token is invalid!"}), 401
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return flask.jsonify({"message": f"Token validation error: {e}"}), 401

        return f(*args, **kwargs)
    return decorated

@app.route('/.well-known/agent.json', methods=['GET'])
def get_agent_card():
    return flask.jsonify(AGENT_CARD)

@app.route('/login', methods=['POST'])
def login():
    # In a real application, you would authenticate a user here (e.g., from a database)
    # For this example, we'll assume any valid POST to /login gets a token
    # You could add basic auth or check for specific credentials if needed.
    # request_data = flask.request.get_json() # if you want to check username/password
    # if request_data.get("username") == "test_user" and request_data.get("password") == "test_pass":
    
    # For simplicity, just issue a token for a generic requesting agent
    payload = {
        'user_id': 'requesting_agent_service_account', # Example claim
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1) # Token expires in 1 hour
    }
    try:
        token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm="HS256")
        logger.info(f"Token issued for user_id: {payload['user_id']}")
        return flask.jsonify({'token': token})
    except Exception as e:
        logger.error(f"Error encoding token: {e}")
        return flask.jsonify({"error": "Could not generate token"}), 500
    # else:
    #    return flask.jsonify({"error": "Invalid credentials"}), 401


@app.route('/submit_task', methods=['POST'])
@token_required # Protect this route
def submit_task():
    if not flask.request.is_json: return flask.jsonify({"error": "Request must be JSON"}), 400
    request_data = flask.request.get_json()
    req_agent_id = request_data.get("requesting_agent_id")
    skill_id = request_data.get("skill_id")
    input_data = request_data.get("input_data")

    if not next((s for s in AGENT_CARD['skills'] if s['id'] == skill_id), None):
        return flask.jsonify({"error": f"Skill '{skill_id}' not supported"}), 400
    if not isinstance(input_data, dict) or 'search_topic' not in input_data or 'extraction_instruction' not in input_data:
         return flask.jsonify({"error": "Invalid input. Expected 'search_topic' & 'extraction_instruction'."}), 400

    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
      "task_id": task_id, "requesting_agent_id": req_agent_id, "skill_id": skill_id,
      "input_data": input_data, "status": "submitted",
      "status_message": "Task received and queued for processing.", "progress_percent": 0,
      "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    UPDATE_QUEUES[task_id] = Queue()
    logger.info(f"Task {task_id} created for skill '{skill_id}'. Initial status: submitted.")

    processing_thread = threading.Thread(target=_process_task, args=(task_id,), daemon=True)
    processing_thread.start()

    return flask.jsonify({
        "task_id": task_id,
        "status": TASKS[task_id]["status"],
        "status_message": TASKS[task_id]["status_message"],
        "updates_url": f"{BASE_URL}{AGENT_CARD['endpoints']['task_updates'].format(task_id=task_id)}"
    }), 202


@app.route('/task_updates/<task_id>', methods=['GET'])
@token_required # Protect this route
def task_updates(task_id):
    if task_id not in TASKS:
        return "Task not found", 404

    def event_stream():
        yield ": connection established\n\n"
        q = UPDATE_QUEUES.get(task_id)
        current_task_data = TASKS.get(task_id)

        if not current_task_data:
            error_event_data = {"task_id": task_id, "status": "error", "status_message": "Task data not found on server."}
            yield f"event: task_error\ndata: {json.dumps(error_event_data)}\n\n"
            return

        initial_event_data = {
            k: v for k, v in current_task_data.items()
            if k in ["task_id", "status", "status_message", "progress_percent", "artefacts", "error_message"]
        }
        yield f"event: task_update\ndata: {json.dumps(initial_event_data)}\n\n"

        if current_task_data.get("status") in ["completed", "failed", "cancelled"]:
            if q:
                try: q.put_nowait(None)
                except Exception: pass
            return

        if not q:
            error_event_data = {"task_id": task_id, "status": "error", "status_message": "Update queue missing for an active task."}
            yield f"event: task_error\ndata: {json.dumps(error_event_data)}\n\n"
            return

        while True:
            try:
                update_message = q.get(timeout=30)
                if update_message is None: break
                event_name = update_message.get('event', 'task_update')
                data_payload = json.dumps(update_message.get("data", {}))
                yield f"event: {event_name}\ndata: {data_payload}\n\n"
                if update_message.get("data", {}).get("status") in ["completed", "failed", "cancelled"]:
                    break
            except Empty:
                task_still_active = TASKS.get(task_id, {}).get("status") not in ["completed", "failed", "cancelled"]
                if not task_still_active: break
                yield ": keepalive\n\n"
            except Exception as e:
                logger.error(f"SSE stream error for task {task_id}: {e}", exc_info=True)
                try:
                    error_payload = json.dumps({"message": f"SSE stream error: {str(e)}"})
                    yield f"event: stream_error\ndata: {error_payload}\n\n"
                except Exception: pass
                break
    return flask.Response(event_stream(), mimetype="text/event-stream")


def _process_task(task_id):
    task_data_ref = TASKS[task_id]
    q = UPDATE_QUEUES[task_id]

    def send_update(status, message, progress, event_type="task_update", artefacts=None, error_msg=None):
        task_data_ref["status"] = status
        task_data_ref["status_message"] = message
        task_data_ref["progress_percent"] = progress
        task_data_ref["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        payload_for_queue = {"task_id": task_id, "status": status, "status_message": message, "progress_percent": progress}
        if artefacts is not None:
            task_data_ref["artefacts"] = artefacts
            payload_for_queue["artefacts"] = artefacts
        if error_msg is not None:
            task_data_ref["error_message"] = error_msg
            payload_for_queue["error_message"] = error_msg
        if q: q.put({"event": event_type, "data": payload_for_queue})
        logger.info(f"[Task {task_id}] Update: {status} ({progress}%) - '{message}'")

    try:
        search_topic = task_data_ref["input_data"]["search_topic"]
        extraction_instruction = task_data_ref["input_data"]["extraction_instruction"]
        send_update("working", "Initializing tools...", 10)

        llm, search_tool = None, None
        try:
            llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_FOR_STUDIO, google_api_key=GOOGLE_AI_STUDIO_API_KEY, convert_system_message_to_human=True)
            search_tool = TavilySearchResults(max_results=3, tavily_api_key=TAVILY_API_KEY)
            logger.info("Langchain tools initialized.")
        except Exception as e:
            err_msg = f"Fatal: Error initializing Langchain tools: {str(e)}"
            logger.error(f"[Task {task_id}] {err_msg}", exc_info=True)
            send_update("failed", err_msg, 10, event_type="task_failure", error_msg=str(e)); return

        send_update("working", f"Searching web for: '{search_topic}'...", 30)
        search_results_raw = []
        try:
            search_results_raw = search_tool.invoke(search_topic)
        except Exception as e:
            err_msg = f"Error during web search: {str(e)}"
            logger.error(f"[Task {task_id}] {err_msg}", exc_info=True)
            send_update("failed", err_msg, 30, event_type="task_failure", error_msg=str(e)); return

        send_update("working", f"Extracting info based on: '{extraction_instruction}'...", 70)
        formatted_prompt_results = "".join(
            f"Result {i+1}:\nTitle: {res.get('title', 'N/A')}\nURL: {res.get('url', 'N/A')}\nSnippet: {res.get('content', 'N/A')}\n\n"
            for i, res in enumerate(search_results_raw) if isinstance(res, dict)
        ) if isinstance(search_results_raw, list) else str(search_results_raw)
        prompt_text = (f"Based on these web search results, follow the instruction.\n"
                       f"Instruction: \"{extraction_instruction}\"\n\n"
                       f"Search Results:\n---\n{formatted_prompt_results}\n---\nExtracted Information:")
        try:
            response = llm.invoke(prompt_text)
            extracted_data = response.content
        except Exception as e:
            err_msg = f"Error during LLM extraction: {str(e)}"
            logger.error(f"[Task {task_id}] {err_msg}", exc_info=True)
            send_update("failed", err_msg, 70, event_type="task_failure", error_msg=str(e)); return

        final_artefacts = {"extracted_data": extracted_data, "source_query": search_topic, "search_results_summary": search_results_raw}
        send_update("completed", "Extraction successful.", 100, event_type="task_completion", artefacts=final_artefacts)
        logger.info(f"[Task {task_id}] Processing completed successfully.")
    except Exception as e:
        err_msg = f"Critical error in task processing: {str(e)}"
        logger.error(f"[Task {task_id}] {err_msg}", exc_info=True)
        send_update("failed", err_msg, task_data_ref.get("progress_percent", 99), event_type="task_failure", error_msg=str(e))
    finally:
        if q: q.put(None)
        logger.info(f"[Task {task_id}] _process_task finished.")

if __name__ == '__main__':
    logger.info(f"Starting {AGENT_NAME} ({AGENT_ID}) on {BASE_URL}:{PORT}")
    logger.info("Dependencies: pip install flask langchain-google-genai langchain-community sseclient-py requests PyJWT")
    app.run(host='localhost', port=PORT, threaded=True)