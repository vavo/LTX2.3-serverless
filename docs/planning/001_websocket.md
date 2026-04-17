# Websocket Runtime Plan

## Goal

Replace ComfyUI `/history/{prompt_id}` polling with websocket-based execution tracking in the current Python runtime without regressing:

- worker-mode workflow execution in `handler.py`
- pod-mode submission flow in `frontend_app.py`
- multi-node routing and failover
- current output payload format for images and videos
- current S3 vs inline-base64 behavior

This is not a rewrite of output handling. It is a runtime communication change first.

## Why This Is Worth Doing

The current code polls ComfyUI in two places:

- `handler.py` uses `wait_for_workflow_completion(...)`
- `frontend_app.py` uses `wait_for_history(...)` and `fetch_history_once(...)`

That works, but it is wasteful, duplicates logic, and makes progress/completion detection slower and more brittle than necessary.

Using ComfyUI websockets should:

- reduce repeated HTTP polling during long renders
- give cleaner completion detection
- create one shared execution-monitoring path for worker and pod modes
- make future progress reporting easier if we decide to expose node-level events later

## Non-Goals

- Do not redesign the public API contract.
- Do not remove support for video outputs.
- Do not switch S3 uploads to a different storage backend.
- Do not mix this with a large `handler.py` refactor unless needed to land the websocket path cleanly.
- Do not switch output retrieval to `/view` in the same change unless video behavior is verified and covered by tests.

## Current Reality

The old websocket planning note in this repo is stale. The current implementation:

- is async and uses `aiohttp`
- supports both images and videos
- uploads with `boto3`, not `rp_upload`
- still reads generated artifacts from `COMFY_OUTPUT_DIR`
- has worker-mode logic in `handler.py`
- has pod/local frontend logic in `frontend_app.py`

Any websocket implementation has to fit that shape, not an older image-only handler.

## Proposed Design

### 1. Add a Shared Comfy Execution Runtime

Create a small shared module for ComfyUI execution lifecycle concerns, for example:

- queue prompt
- open websocket
- monitor events for a specific `prompt_id`
- fall back or fail clearly on disconnect/timeout
- fetch final history entry after completion

Likely module name:

- `comfy_runtime.py`

Keep it focused. This module should not own Redis, S3, cache, or response shaping.

### 2. Use Async Websockets

Do not use the blocking `websocket-client` API inside the async runtime.

Use `aiohttp` websocket support so the worker and frontend stay within the existing async model:

- `session.ws_connect(...)`
- async receive loop
- timeout handling with `asyncio`

If `websocket-client` remains in `requirements.txt`, treat it as dependency cleanup work, not a design dependency.

### 3. Queue Workflow With `client_id`

For each submitted workflow:

- generate a unique `client_id`
- connect to `ws://<node>/ws?clientId=<client_id>` before queueing
- submit `/prompt` with:

```json
{
  "prompt": { "...": "..." },
  "client_id": "generated-client-id"
}
```

The websocket monitor should only consider events for the matching `prompt_id`.

### 4. Completion Detection Strategy

Monitor websocket messages until ComfyUI signals completion for the queued prompt.

Primary success condition:

- `executing` event for the matching `prompt_id` where `data.node` is `null`

Also handle:

- malformed JSON frames
- binary/non-JSON frames that can be ignored safely
- timeout while waiting for completion
- websocket disconnect before completion

After completion, do one final `GET /history/{prompt_id}` and return the prompt-specific history entry.

That keeps output discovery aligned with the current output payload code and avoids changing artifact handling in the same PR.

### 5. Keep Output Retrieval As-Is For The First Slice

For the first implementation:

- keep `handler.py` reading generated files from `COMFY_OUTPUT_DIR`
- keep `frontend_app.py` serving local files through `/api/comfy-output`
- keep output shaping through `workflow_support.collect_output_entries(...)`

Reason:

- current code supports both images and videos
- `/view` changes are a separate concern
- bundling websocket migration with output transport changes would make regressions harder to localize

If filesystem pickup later proves unreliable, that can be a follow-up task with explicit video coverage.

## Implementation Tasks

### Phase 1: Shared Runtime

1. Create a shared async helper module for ComfyUI execution.
2. Move duplicated prompt submission and completion waiting logic out of `handler.py` and `frontend_app.py`.
3. Keep configuration explicit where practical:
   - target node
   - timeout
   - prompt payload

Suggested helper surface:

- `queue_prompt(...)`
- `wait_for_prompt_via_websocket(...)`
- `execute_prompt_and_get_history(...)`

Exact naming is not important. Ownership boundaries are.

### Phase 2: Worker Integration

Update `handler.py` so workflow jobs:

1. select the target node as they do now
2. queue the workflow with `client_id`
3. wait via websocket instead of `/history` polling
4. fetch final history once
5. continue using existing output payload builders

Important:

- preserve failover behavior
- define whether websocket disconnect counts as node failure immediately or only after a bounded retry policy
- keep existing overall render timeout behavior

### Phase 3: Pod/Frontend Integration

Update `frontend_app.py` pod mode:

1. submit local workflow with `client_id`
2. either:
   - wait for completion server-side and return completed output directly, or
   - keep the current two-step submit/status API and back the status endpoint with shared websocket-aware state

Preferred first step:

- keep the existing `/api/pod-submit` and `/api/pod-submit/{prompt_id}` contract
- reduce implementation churn

That said, the current pod mode still polls status from the browser and backend. Once websocket runtime exists, there is a reasonable case for simplifying that flow later.

### Phase 4: Config Cleanup

Only add websocket-related config if it is genuinely needed.

Possible config:

- `COMFY_EXECUTION_TIMEOUT_SECONDS`
- `WEBSOCKET_RECONNECT_ATTEMPTS`
- `WEBSOCKET_RECONNECT_DELAY_S`
- `WEBSOCKET_TRACE`

Do not add knobs just to feel productive.

If reconnect behavior is added, document exactly:

- what qualifies for reconnect
- whether reconnect resumes waiting for the same `prompt_id`
- when the node is considered failed

## Failure Handling

The websocket path should fail in ways that fit the current runtime model.

### Worker Mode

If websocket monitoring fails:

- treat the event as node execution failure
- trip the existing circuit breaker for that node when appropriate
- allow the existing failover path to retry on another node if the workflow is safe to resubmit

Be careful here:

- resubmitting after a late websocket disconnect can duplicate work if ComfyUI kept running
- if retry behavior is retained, document the duplication risk clearly

### Pod Mode

If websocket monitoring fails in local pod mode:

- return a clear 502/504 class error
- clean up staged input files
- avoid leaving in-memory prompt tracking in a misleading state

## Testing

### Unit Tests

Add or update tests for:

- prompt submission includes `client_id`
- websocket completion detection for the matching `prompt_id`
- unrelated websocket events are ignored
- disconnect/timeout handling
- final history fetch after websocket completion
- worker failover behavior when websocket monitoring fails
- pod submit cleanup on websocket failure

Also fix or replace stale tests that still target the old handler API.

### Integration Tests

Run local Docker validation after implementation:

```bash
docker-compose down
docker build --target base --platform linux/amd64 -t ltx23-worker:dev .
docker-compose up -d
```

Then verify:

- workflow job success path
- pod submit success path
- image outputs
- video outputs
- S3 mode if configured
- inline mode without S3

Remember: handler changes require a full image rebuild in this repo.

## Suggested Delivery Slice

Best first PR-sized chunk:

1. add shared async Comfy execution runtime
2. migrate `handler.py` workflow execution to websockets
3. keep final history lookup and current output retrieval unchanged
4. add tests for the shared runtime

Second chunk:

1. migrate `frontend_app.py` pod mode to the shared runtime
2. remove duplicated polling helpers
3. update docs that still claim websockets are already in use

## Success Criteria

- No `/history` polling loop remains in the worker workflow execution path.
- Worker output payloads remain backward-compatible.
- Image and video outputs still work.
- Pod mode keeps working locally.
- Docs describe reality instead of aspiration.

## Follow-Up Work

After the websocket migration lands cleanly, consider separate follow-ups:

- evaluate `/view` for image retrieval if filesystem pickup becomes a real issue
- decide whether video retrieval should also move away from direct file access
- simplify pod-mode submit/status flow
- continue the broader shared-runtime refactor from `004_refactor_plan.local.md`
