# Technical Spec: Phase 3 — Real-Time Push Events

## Overview

Replace polling-based graph updates with event-driven push via SSE (Server-Sent Events). Editors get instant graph state updates as files change.

## Components

### 3a. Event Bus (`code_review_graph/push.py`)

```python
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional
import json
import time

class EventType(Enum):
    NODE_ADDED = "node_added"
    NODE_UPDATED = "node_updated"
    NODE_REMOVED = "node_removed"
    EDGE_ADDED = "edge_added"
    EDGE_REMOVED = "edge_removed"
    COMMUNITY_CHANGED = "community_changed"
    FLOW_CHANGED = "flow_changed"
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"

@dataclass
class GraphEvent:
    type: EventType
    payload: dict
    timestamp: float = field(default_factory=time.time)
    
    def to_sse(self) -> str:
        return f"event: {self.type.value}\ndata: {json.dumps(self.payload)}\n\n"

class EventBus:
    """Fan-out event bus with per-subscriber asyncio.Queue."""
    
    def __init__(self, max_queue_size: int = 100):
        self._subscribers: dict[str, asyncio.Queue] = {}
        self._max_queue_size = max_queue_size
    
    def subscribe(self, client_id: str) -> None: ...
    def unsubscribe(self, client_id: str) -> None: ...
    
    async def publish(self, event: GraphEvent) -> None:
        """Publish to all subscribers. Drop if queue full (backpressure)."""
        ...
    
    async def stream(self, client_id: str) -> AsyncIterator[str]:
        """Yield SSE-formatted events for a subscriber."""
        ...

# Module-level singleton
_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
```

### 3b. SSE Endpoint (in `main.py`)

```python
# Add to FastMCP server setup
@app.route("/graph-events")
async def graph_events_stream(request):
    """SSE endpoint for real-time graph updates."""
    client_id = request.query.get("client_id", str(uuid4()))
    bus = get_event_bus()
    bus.subscribe(client_id)
    
    async def event_generator():
        try:
            async for event_data in bus.stream(client_id):
                yield event_data
        finally:
            bus.unsubscribe(client_id)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 3c. Split Incremental Pipeline (`code_review_graph/incremental.py`)

```
Current: fs_event → parse → update_all → postprocess_all

New:     fs_event → debounce(50ms) → parse → update_nodes_edges
                                              ↓ (emit SSE: fast)
                                     [timer/threshold]
                                              ↓
                                     recompute_communities
                                     recompute_flows
                                     rebuild_fts (emit SSE: full)
```

**Debounce rules:**
- Single file: 50ms
- Batch (save-all): 200ms
- Threshold for full postprocess: 10 changed nodes OR 60 seconds elapsed

### 3d. FS Watcher Integration

```python
# Optional: only if watchfiles available
try:
    from watchfiles import awatch
    HAS_WATCHFILES = True
except ImportError:
    HAS_WATCHFILES = False

async def watch_and_update(repo_root: str, db_path: str) -> None:
    """Watch filesystem and trigger incremental updates."""
    if not HAS_WATCHFILES:
        logger.info("watchfiles not installed, real-time push disabled")
        return
    ...
```

**Optional dependency:** `watchfiles` (not required, graceful fallback)

## Migration

No new tables needed. Event bus is in-memory only.

## Testing

```
tests/test_push.py:
  - test_subscribe_unsubscribe
  - test_publish_to_multiple_subscribers
  - test_backpressure_drops_on_full_queue
  - test_sse_format
  - test_stream_yields_events

tests/test_incremental_split.py:
  - test_fast_path_emits_node_events
  - test_full_postprocess_triggered_by_threshold
  - test_debounce_batches_rapid_changes
```

## Client Integration

Clients connect to `GET /graph-events?client_id=xxx` and receive:

```
event: node_updated
data: {"qn": "MyClass.method", "file": "src/foo.py", "kind": "Function"}

event: build_completed  
data: {"duration_ms": 150, "nodes_changed": 3}
```
