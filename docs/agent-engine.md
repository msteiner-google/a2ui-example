# Agent Engine Deployment Guide & Changes

This document outlines the specific configuration and code changes required to deploy the Insurance Assistant agent to Vertex AI Agent Engine and register it with Gemini Enterprise.

## 1. OAuth Authorization Setup

Before deployment, an OAuth authorization resource must be registered with the Discovery Engine API. This allows the agent to handle server-side OAuth2 flows.

### Endpoint Mapping
- **Global**: `https://discoveryengine.googleapis.com/v1alpha`
- **EU Multi-region**: `https://eu-discoveryengine.googleapis.com/v1alpha` (Requires an existing data store in the region).

### Registration Command
Use a `curl` command to create the authorization. Note that the `authorizationId` should be a unique identifier.

```bash
curl -X POST \
   -H "Authorization: Bearer $(gcloud auth print-access-token)" \
   -H "Content-Type: application/json" \
   -H "X-Goog-User-Project: <PROJECT_ID>" \
   "https://discoveryengine.googleapis.com/v1alpha/projects/<PROJECT_ID>/locations/global/authorizations?authorizationId=<AUTH_ID>" \
   -d '{
      "name": "projects/<PROJECT_ID>/locations/global/authorizations/<AUTH_ID>",
      "serverSideOauth2": {
         "clientId": "<OAUTH_CLIENT_ID>",
         "clientSecret": "<OAUTH_CLIENT_SECRET>",
         "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id=<OAUTH_CLIENT_ID>&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
         "tokenUri": "https://oauth2.googleapis.com/token"
      }
   }'
```

## 2. Environment Configuration (`.env`)

The `.env` file must be correctly formatted for the `deploy.py` script and the remote environment.

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `PROJECT_ID` | The GCP Project ID. | `gemini-enterprise-test-495411` |
| `LOCATION` | The Vertex AI region for Reasoning Engines. | `europe-west4` |
| `STORAGE_BUCKET` | Staging bucket (must start with `gs://`, no trailing slash). | `gs://my-bucket` |
| `GEMINI_ENTERPRISE_APP_ID` | The ID of the Discovery Engine engine. | `test-agent-engine-a2a_...` |
| `AGENT_AUTHORIZATION` | The **full resource name** of the authorization. | `projects/.../locations/global/authorizations/v3` |

## 3. Code Architecture Changes

### Agent Executor (`agent_engine_executor.py`)
To ensure compatibility with Agent Engine and proper UI rendering in Gemini Enterprise, the executor was updated with:

1.  **Task Lifecycle Management**: Explicitly calls `new_task`, `updater.start_work()`, `updater.add_artifact()`, and `updater.complete()`. Without these, the UI may not receive updates or show the final message.
2.  **Task State**: Defaults `final_state` to `TaskState.completed` for chat turns to prevent the client from polling indefinitely.
3.  **Deserialization Support**: The `__init__` method handles `agent_card` being passed as either a dictionary (standard during remote deserialization) or an `AgentCard` object.
4.  **A2UI Activation**: Uses `VERSION_0_8 = "0.8"` to ensure the UI extension is recognized.

### Deployment Script (`deploy.py`)
1.  **Module Imports**: Changed to absolute package imports (e.g., `from .agent import ...`) to support running via `python -m adk2.deploy`.
2.  **Executor Configuration**: Passes the `agent_card` explicitly via `agent_executor_kwargs` in the `A2aAgent` constructor.
3.  **Bundling**: Simplified `extra_packages` to include the entire `adk2` directory. This ensures all sub-modules (`models`, `subagents`, `data`) are available in the remote environment.
4.  **API Payload**: Corrected field names for the registration payload: `authorizationConfig` and `agentAuthorization`.

## 5. Detailed Executor Comparison

Understanding why the `AgentEngineExecutor` works where the previous one failed is key to mastering Agent Engine deployments.

| Feature | Previous Executor (Legacy) | Agent Engine Executor (Working) | Why it matters |
| :--- | :--- | :--- | :--- |
| **Task Creation** | Assumed `task_id` was already present in context. | Checks `context.current_task`; if missing, creates one with `new_task()`. | Without a valid Task object, the system cannot track the request status or map it to a specific UI session. |
| **Task Lifecycle** | Called `updater.update_status()` directly. | Calls `updater.start_work()` → `updater.add_artifact()` → `updater.complete()`. | `complete()` explicitly signals the frontend to stop polling. Direct status updates without a terminal state caused the "stuck" behavior. |
| **Response Delivery** | Sent parts via `Message` object in status update. | Wraps response parts as an **artifact** named `"response"`. | Gemini Enterprise specifically looks for a `"response"` artifact to render the final message and its associated UI components. |
| **Serialization** | Expected `AgentCard` type in `__init__`. | Handles `AgentCard | dict` in `__init__`. | Remote environments often deserialize Pydantic models as dictionaries. This prevents a `TypeError` during server-side startup. |
| **UI Activation** | Relied on dynamic detection via `try_activate...`. | Hardcoded `VERSION_0_8` for reliability. | Ensures the A2UI extension is always reported as active, preventing the frontend from falling back to a "text-only" experience. |

### Summary of the "Stuck Polling" Issue
The primary reason the previous executor was "stuck" was that it never reached a definitive `terminal` state (like `COMPLETED` or `FAILED`) that the Gemini Enterprise frontend could recognize. By using the explicit `updater.complete()` method, we ensure the backend and frontend stay in sync, and the user receives the message as soon as processing is finished.
