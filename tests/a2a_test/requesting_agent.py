# requesting_agent.py (Manual SSE Handling with requests)

import requests
import json
import time
import logging
# import sseclient # NO LONGER IMPORTING THE PROBLEMATIC LIBRARY
import os
import sys
import asyncio
import random
import warnings
import uuid
from inspect import signature

# --- Standard Setup (Logging, ADK, Helpers - Keep as before) ---
warnings.filterwarnings("ignore")
logger = logging.getLogger("ADK_Requesting_Agent_ManualSSE")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

YOUR_GOOGLE_AI_STUDIO_KEY = "AIzaSyCW0SFlsOvlQLYm2__ROSrFNH0V1wPnr9k"
os.environ["GOOGLE_API_KEY"] = YOUR_GOOGLE_AI_STUDIO_KEY

try:
    import google.generativeai
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types
    ADK_AVAILABLE = True
    google.generativeai.configure(api_key=YOUR_GOOGLE_AI_STUDIO_KEY)
except ImportError:
    logger.critical("Required Google libraries not found.")
    ADK_AVAILABLE = False
    if __name__ == '__main__': sys.exit(1)
except Exception as e:
    logger.critical(f"Error during ADK/google.generativeai setup: {e}")
    ADK_AVAILABLE = False
    if __name__ == '__main__': sys.exit(1)

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
MODEL_FOR_ADK_LLM = "gemini-2.0-flash"
REQUESTING_AGENT_ID = "adk-req-jwt-manualsse-001"
SPECIALIST_AGENT_BASE_URL = "http://localhost:5001"
REQUIRED_SKILL_ID = "browse_extract"
SPECIALIST_AGENT_AUTH_TOKEN = None

# --- ADK and other helper functions (generate_random_question_tool, etc.) ---
def generate_random_question_tool() -> str: logger.debug("--- ADK Tool: generate_random_question_tool called ---"); questions = ["What's a simple thing that brings you joy?", "Describe your perfect day.", "What's a skill you'd like to learn?"]; chosen_question = random.choice(questions); logger.debug(f"--- ADK Tool: Generated question: '{chosen_question}' ---"); return chosen_question
def create_local_question_agent(): logger.info("Defining the local ADK Question Generator Agent..."); agent = Agent( name="local_question_generator_v15_manualsse", model=MODEL_FOR_ADK_LLM, description="Generates random questions.", instruction="Use 'generate_random_question_tool' to get a question. Return ONLY the question text.", tools=[generate_random_question_tool], ); logger.info(f"✅ Local ADK Agent '{agent.name}' created."); return agent
async def _get_adk_question_async(agent: Agent):
    if not agent: return "Error: ADK Agent not created."
    session_service = InMemorySessionService(); session_id = f"temp_q_session_{uuid.uuid4()}"; user_id = "local_adk_user"; app_name = "local_question_gen"
    session = session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    content = genai_types.Content(role='user', parts=[genai_types.Part(text="Get question")])
    final_question = "Error: Failed to get question from ADK agent."
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response():
                if event.content and event.content.parts: final_question = event.content.parts[0].text
                else: logger.warning("ADK Agent final response had no content.")
                break
    except Exception as e: logger.error(f"❌ Error running local ADK agent: {e}", exc_info=True); final_question = f"Error: ADK Exception - {e}"
    return final_question
def get_random_question_via_adk(agent: Agent):
    if not agent: return generate_random_question_tool() + " (ADK Agent Uninit Fallback)"
    logger.info("Requesting question from local ADK agent..."); return asyncio.run(_get_adk_question_async(agent)) # Simplified error handling
def discover_specialist(base_url): logger.info(f"Attempting discovery: Fetching Agent Card from {base_url}/.well-known/agent.json"); response = requests.get(f"{base_url}/.well-known/agent.json", timeout=10); response.raise_for_status(); return response.json()
def authenticate_with_specialist(agent_card):
    global SPECIALIST_AGENT_AUTH_TOKEN; logger.info(f"Attempting auth at {agent_card['url']}{agent_card['capabilities']['auth_info']['login_endpoint']}"); response = requests.post(f"{agent_card['url']}{agent_card['capabilities']['auth_info']['login_endpoint']}", timeout=10); response.raise_for_status(); SPECIALIST_AGENT_AUTH_TOKEN = response.json().get("token"); logger.info("Auth successful."); return True
def delegate_task(agent_card, skill_id, task_input_data):
    submit_url = f"{agent_card['url']}{agent_card['endpoints']['submit_task']}"; payload = {"requesting_agent_id": REQUESTING_AGENT_ID, "skill_id": skill_id, "input_data": task_input_data}; headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if SPECIALIST_AGENT_AUTH_TOKEN: headers['Authorization'] = f"Bearer {SPECIALIST_AGENT_AUTH_TOKEN}"
    auth_summary = headers.get('Authorization', 'No Auth'); auth_summary = auth_summary[:20]+"..." if len(auth_summary)>30 else auth_summary; logger.info(f"Delegating task to {submit_url} (Auth: {auth_summary})")
    response = requests.post(submit_url, json=payload, headers=headers, timeout=15); response.raise_for_status(); return response.json()
# --- End Helper Functions ---

# --- Manual SSE Parser ---
def parse_sse_event(raw_lines):
    """Parses a list of raw string lines into an SSE event dict."""
    event = {'event': 'message', 'data': '', 'id': None, 'retry': None}
    data_lines = []
    for line in raw_lines:
        if not line: continue # Skip empty lines within event
        if line.startswith(':'): continue # Skip comments

        field, value = '', ''
        if ':' in line:
            field, value = line.split(':', 1)
            value = value.lstrip(' ') # Remove leading space if present
        else:
            field = line # Whole line is field name (no value)

        if field == 'event': event['event'] = value
        elif field == 'data': data_lines.append(value)
        elif field == 'id': event['id'] = value
        elif field == 'retry':
            try: event['retry'] = int(value)
            except (ValueError, TypeError): pass # Ignore invalid retry values
        # Ignore other fields

    event['data'] = '\n'.join(data_lines)
    return event
# --- End Manual SSE Parser ---


def listen_for_updates(updates_url):
    if not updates_url:
        logger.error("Cannot listen: updates_url is missing.")
        return None
    logger.info(f"Connecting to SSE stream MANUALLY: {updates_url}")

    final_result = None
    response = None # To hold the requests response

    headers = {'Accept': 'text/event-stream'}
    if SPECIALIST_AGENT_AUTH_TOKEN:
        headers['Authorization'] = f"Bearer {SPECIALIST_AGENT_AUTH_TOKEN}"
    
    auth_summary = headers.get('Authorization', 'No Auth')
    if len(auth_summary) > 30: auth_summary = auth_summary[:20] + "..."

    logger.info(f"Making GET request for SSE stream with headers (Auth: {auth_summary})")

    try:
        response = requests.get(
            updates_url,
            headers=headers,
            stream=True,
            timeout=(10, 60) # (connect_timeout, read_timeout) - adjust as needed
        )
        response.raise_for_status()
        logger.info(f"Connected to stream (status {response.status_code}). Processing lines...")

        event_lines = []
        event_count = 0
        for line in response.iter_lines(decode_unicode=True):
            # iter_lines(decode_unicode=True) should yield strings
            if line is None: # Handle potential None values if stream ends abruptly
                continue
                
            logger.debug(f"Raw line: '{line}'")
            
            if line == '': # An empty line signifies the end of an event
                if event_lines:
                    event_count += 1
                    parsed_event = parse_sse_event(event_lines)
                    logger.debug(f"Parsed Event {event_count}: {parsed_event}")
                    
                    if not parsed_event.get('data'):
                        logger.debug("Skipping event with no data.")
                        event_lines = []
                        continue
                        
                    try:
                        event_data = json.loads(parsed_event['data'])
                        task_id_from_event = event_data.get("task_id", "N/A")
                        status = event_data.get("status")
                        message = event_data.get("status_message", "")
                        progress = event_data.get("progress_percent")
                        prog_str = f" ({progress}%)" if progress is not None else ""
                        logger.info(f"   [Task {task_id_from_event}] Status: {status}{prog_str} - '{message}'")

                        if status in ["completed", "failed", "cancelled"]:
                            final_result = {"status": status, "artefacts": event_data.get("artefacts"), "error": event_data.get("error_message")}
                            logger.info(f"Terminal event for task {task_id_from_event}. Stopping stream processing.")
                            # Break from the line iteration loop
                            # Note: Doesn't explicitly close response here, finally block will do it.
                            return final_result # Exit function upon terminal event

                    except json.JSONDecodeError:
                        logger.warning(f"   JSON parse error for SSE data: {parsed_event['data'][:200]}...")
                    except Exception as e_proc:
                        logger.error(f"   Error processing parsed SSE event: {e_proc}", exc_info=True)
                    
                    event_lines = [] # Reset for next event
            else:
                event_lines.append(line)

        # If the loop finishes without finding a terminal event (e.g., stream closed by server)
        if not final_result:
             logger.warning("SSE stream finished without a terminal event detected.")

    except requests.exceptions.HTTPError as e:
        logger.error(f"SSE HTTPError for {updates_url}: {e}", exc_info=True)
        if e.response is not None: logger.error(f"Response: {e.response.status_code}, Body: {e.response.text[:500]}")
    except requests.exceptions.RequestException as e:
        logger.error(f"SSE RequestException for {updates_url}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error listening to {updates_url}: {e}", exc_info=True)
    finally:
        logger.info(f"Stopping manual SSE listening for {updates_url}.")
        if response: # Close the requests response object
            try: response.close(); logger.info("Requests response closed.")
            except Exception as e: logger.error(f"Error closing requests response: {e}", exc_info=True)
        logger.info(f"Finished manual SSE listening logic for {updates_url}.")
        # Return whatever final_result holds (could be None if no terminal event received)
        return final_result


if __name__ == "__main__":
    # --- main execution block ---
    logger.info(f"🚀 Starting {REQUESTING_AGENT_ID} 🚀")
    # ... (rest of main is the same, calls the new listen_for_updates) ...
    if not ADK_AVAILABLE: logger.critical("Google ADK/GenAI libraries not available."); sys.exit(1)
    local_adk_agent = create_local_question_agent()
    if not local_adk_agent: logger.critical("Failed to create local ADK agent. Exiting."); sys.exit(1)
    logger.info("\n--- Step 1: Discovering Specialist Agent ---")
    agent_card = discover_specialist(SPECIALIST_AGENT_BASE_URL)
    if not agent_card: logger.critical(f"Could not discover {SPECIALIST_AGENT_BASE_URL}. Exiting."); sys.exit(1)
    logger.info(f"Discovered: {agent_card.get('name')} at {agent_card.get('url')}")
    logger.info("\n--- Step 1.5: Authenticating with Specialist Agent ---")
    if agent_card.get("capabilities", {}).get("auth_required", False):
        if not authenticate_with_specialist(agent_card): logger.critical("Authentication failed. Exiting."); sys.exit(1)
    else: logger.info("Specialist does not require authentication per its card.")
    logger.info("\n--- Step 2: Generating Task Input ---")
    generated_question = get_random_question_via_adk(local_adk_agent)
    if "Error:" in generated_question: logger.warning(f"Using potentially error/fallback question: {generated_question}")
    if "ADK Exception" in generated_question: logger.critical("ADK question gen failed. Exiting."); sys.exit(1)
    task_input = {"search_topic": generated_question, "extraction_instruction": f"Summarize web results for: '{generated_question}'"}
    logger.info(f"Task input: {json.dumps(task_input)}")
    logger.info("\n--- Step 3: Delegating Task ---")
    delegation_response = delegate_task(agent_card, REQUIRED_SKILL_ID, task_input)
    if not delegation_response or "task_id" not in delegation_response: logger.critical("Task delegation failed. Exiting."); sys.exit(1)
    task_id, updates_url = delegation_response["task_id"], delegation_response["updates_url"]
    logger.info(f"Task {task_id} submitted. Updates at: {updates_url}")
    logger.info("\n--- Step 4: Listening for Updates ---")
    final_result = listen_for_updates(updates_url) # CALLS THE NEW MANUAL FUNCTION
    logger.info("\n--- Step 5: Processing Final Result ---")
    if final_result:
        logger.info(f"Final result for Task {task_id}: Status: {final_result.get('status', 'N/A').upper()}")
        if final_result.get("status") == "completed": logger.info(f"Artefacts:\n{json.dumps(final_result.get('artefacts'), indent=2)}")
        elif final_result.get("status") == "failed": logger.error(f"Error Reported: {final_result.get('error', 'N/A')}")
    else: logger.warning(f"No definitive final result for Task {task_id}.")
    logger.info(f"🏁 {REQUESTING_AGENT_ID} finished. 🏁")