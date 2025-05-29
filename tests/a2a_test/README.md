# Agent-to-Agent (a2a) Communication: A Five-Step Protocol Example

This document outlines the five-step protocol for inter-agent communication as exemplified by the provided `requesting_agent.py` and `specialist_agent.py` scripts. This protocol facilitates task delegation and asynchronous result retrieval between autonomous AI agents.

## Introduction

The agent-to-agent (a2a) communication framework enables a **Requesting Agent** to discover and utilize the capabilities of a **Specialist Agent**. The process is designed to be asynchronous, allowing the Requesting Agent to submit a task and receive updates, including the final result, without blocking its own operations. This is primarily achieved using Server-Sent Events (SSE) for real-time updates.

The core interaction revolves around a five-step protocol:

1.  **Discovery**: The Requesting Agent finds the Specialist Agent and learns about its capabilities.
2.  **Task Input Generation**: The Requesting Agent prepares the necessary input for the desired task.
3.  **Task Delegation**: The Requesting Agent formally submits the task to the Specialist Agent.
4.  **Update Listening**: The Requesting Agent listens for real-time progress updates and the final outcome from the Specialist Agent.
5.  **Result Processing**: The Requesting Agent processes the final result received from the Specialist Agent.

Let's delve into what each agent does at every step of this protocol.

---

## The Five-Step Protocol

### Step 1: Discovering Specialist Agent

In this initial step, the Requesting Agent needs to locate the Specialist Agent and understand what skills it offers.

* **Requesting Agent:**
    * Initiates discovery by attempting to fetch an "Agent Card" from a known base URL of the Specialist Agent.
    * It makes an HTTP GET request to a standardized endpoint, typically `/.well-known/agent.json`, on the Specialist Agent's server.
    * Upon successful retrieval, it parses the Agent Card (a JSON object) which contains crucial metadata about the Specialist Agent, including its ID, name, description, available skills, and the specific endpoints for interacting with it (like task submission and update streaming).

* **Specialist Agent:**
    * Hosts an HTTP server (e.g., using Flask).
    * Exposes a `/.well-known/agent.json` endpoint.
    * When a GET request hits this endpoint, the Specialist Agent responds with its `AGENT_CARD` in JSON format. This card details its identity, capabilities (e.g., asynchronous operation, SSE for updates), and the specific skills it offers, like "browse_extract" in the example, along with descriptions for input and output.

### Step 2: Generating Task Input

Once the Specialist Agent is discovered and its capabilities are known, the Requesting Agent prepares the data required for the specific skill it wants to utilize.

* **Requesting Agent:**
    * Determines the skill it needs (e.g., `browse_extract`).
    * Generates or gathers the necessary input data for that skill. In the example, it uses an internal ADK (Agent Development Kit) agent to generate a random question, which becomes the `search_topic`.
    * It then formulates an `extraction_instruction` based on this topic.
    * This input data is structured as a dictionary, for example: `{"search_topic": "some question", "extraction_instruction": "Summarize web results for: 'some question'"}`.

* **Specialist Agent:**
    * Remains passive during this step, awaiting a task submission. Its Agent Card has already defined the expected input structure for its skills.

### Step 3: Delegating Task

With the task input ready, the Requesting Agent formally delegates the task to the Specialist Agent.

* **Requesting Agent:**
    * Uses the `submit_task` endpoint URL (obtained from the Specialist Agent's card in Step 1) to send the task.
    * Makes an HTTP POST request to this endpoint.
    * The payload of this request is a JSON object containing:
        * `requesting_agent_id`: Identifier of the agent making the request.
        * `skill_id`: The specific skill to be invoked on the Specialist Agent.
        * `input_data`: The structured input generated in Step 2.
    * Upon successful submission, it expects a JSON response from the Specialist Agent. This response typically includes a unique `task_id` for tracking, the initial `status` of the task (e.g., "submitted"), a human-readable `status_message`, and critically, an `updates_url`. This URL will be used in the next step to listen for real-time updates.

* **Specialist Agent:**
    * Its `/submit_task` endpoint receives the POST request.
    * It validates the incoming JSON payload, checking for required fields like `skill_id` and the structure of `input_data` against the chosen skill's requirements.
    * If the request is valid:
        * It generates a unique `task_id` for this new task.
        * Stores the task details (including input, requesting agent ID, and initial status "submitted") in an internal dictionary (`TASKS`).
        * Creates a dedicated message queue (`UPDATE_QUEUES`) for this `task_id` to manage status updates.
        * Crucially, it launches the actual task processing in a separate, non-blocking thread (e.g., `_process_task`). This ensures the submission endpoint can respond quickly.
        * It then sends back an HTTP 202 Accepted response containing the `task_id`, initial `status`, `status_message`, and the `updates_url` (e.g., `http://localhost:5001/task_updates/{task_id}`).

### Step 4: Listening for Updates

The task is now with the Specialist Agent. The Requesting Agent needs to listen for progress updates and the final result. This is where Server-Sent Events (SSE) come into play.

* **Requesting Agent:**
    * Uses the `updates_url` (received in Step 3) to establish an SSE connection.
    * It employs an SSE client library (like `sseclient-py`) to connect to this streaming endpoint.
    * Once connected, it listens for events. Each event typically provides data like the `task_id`, current `status` (e.g., "working", "completed", "failed"), `status_message`, `progress_percent`, and any generated `artefacts` or `error_message`.
    * The Requesting Agent logs these updates, allowing for real-time monitoring of the task's progress.
    * It continues to listen until it receives a terminal event (e.g., "completed" or "failed"), at which point it will typically close the connection and proceed to the final step.

* **Specialist Agent:**
    * Its `/task_updates/{task_id}` endpoint handles incoming SSE connection requests from the Requesting Agent.
    * Upon connection, it first sends the current state of the task.
    * Then, it continuously checks the task-specific update queue (populated by the `_process_task` thread) for new messages.
    * The `_process_task` thread, running asynchronously, performs the actual work:
        * It initializes necessary tools (e.g., Langchain with Tavily Search and a Google Generative AI model).
        * It performs actions like web searches based on the `search_topic` and extracts information using the LLM based on the `extraction_instruction`.
        * Periodically, it sends updates about its progress (e.g., "Initializing tools...", "Searching web...", "Extracting info...") by putting messages into the task's queue. These messages include the status, a descriptive message, and progress percentage.
        * These queued messages are picked up by the `task_updates` SSE handler and formatted into SSE events (e.g., `event: task_update\ndata: {...json...}\n\n`).
        * If the task completes successfully, `_process_task` sends a final "completed" status with the resulting `artefacts`.
        * If an error occurs at any stage, it sends a "failed" status with an `error_message`.
        * Finally, `_process_task` signals the SSE stream handler (by putting a `None` or sentinel value in the queue) that the task is finished, allowing the SSE stream for that task to close gracefully.

### Step 5: Processing Final Result

Once the Specialist Agent signals that the task is finished (either completed or failed), the Requesting Agent processes the outcome.

* **Requesting Agent:**
    * The `listen_for_updates` function, after receiving a terminal SSE event, returns the final aggregated result. This result usually contains the final `status`, any `artefacts` produced if the task was successful, or an `error_message` if it failed.
    * The main part of the Requesting Agent then takes this final result:
        * If the status is "completed", it logs and potentially utilizes the `artefacts` (e.g., the extracted data and search summary).
        * If the status is "failed", it logs the reported `error`.
    * At this point, the interaction for this specific task is considered complete from the Requesting Agent's perspective.

* **Specialist Agent:**
    * Its primary role in this step is to have successfully transmitted the final state (completion with artefacts or failure with error) via the SSE stream in Step 4.
    * The `_process_task` thread ensures that the shared task data (`TASKS[task_id]`) is updated with the final status and output. It may keep this information for a certain period for auditing or late-retrieval purposes, though the example notes that a more robust cleanup mechanism would be ideal in a production system.

---

This five-step protocol, leveraging HTTP for discovery and task submission, and Server-Sent Events for asynchronous updates, provides a robust and flexible way for AI agents to collaborate and delegate tasks. The use of clear contracts (Agent Cards) and standardized communication patterns is key to its effectiveness.