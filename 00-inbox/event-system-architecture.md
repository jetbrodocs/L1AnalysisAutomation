# Event System Architecture

This document describes the core architecture of the event sourcing system that underpins this platform. The system is a general-purpose event engine -- it does not prescribe any specific business process. You define the events, the data they carry, the rules that govern them, and the reports they feed into. The system records them, connects them, and keeps everything consistent.

The goal is to give you enough understanding to design any process on top of this foundation.

---

## Core Concept

Every state change in the system is recorded as an immutable event in a single append-only table called `movement_events`. These events are the **source of truth**. All other tables (items, locations, users, inventory levels, etc.) are **projections** -- derived read models that are computed from events and can theoretically be rebuilt from scratch by replaying the event log.

The fundamental flow is:

```
User Action
  -> API Endpoint (validates input, checks permissions)
    -> EventService.create_event() (writes event to the store)
      -> ProjectionService.apply_event() (updates derived tables)
        -> Single atomic commit (event + projections together)
```

Nothing mutates business state outside of this flow.

---

## The Event Store

### The `movement_events` Table

This is the one table you must understand completely. Every row is a fact that happened -- it is never updated or deleted.

| Field | Type | Purpose |
|---|---|---|
| `id` | UUID | Auto-generated primary key |
| `event_type` | String(100) | What happened. SCREAMING_SNAKE_CASE, enforced by a CHECK constraint (`^[A-Z][A-Z0-9_]*$`). Examples: `ITEM_CREATED`, `GOODS_RECEIVED`, `STOCK_MOVED` |
| `event_version` | Integer | Schema version for this event type (defaults to 1). Allows evolving payload formats over time |
| `idempotency_key` | String(255) | Optional client-provided key for deduplication. Has a unique constraint -- the system will reject a second event with the same key |
| `payload` | JSONB | The event-specific data. This is the core content -- what was created, what changed, quantities, IDs, etc. Structure varies by event type |
| `event_metadata` | JSONB | Contextual information that is not part of the business payload. Things like `correlation_id`, `source` system, etc. |
| `actor_id` | UUID (FK -> users) | Who performed this action |
| `actor_type` | String(50) | Type of actor, defaults to `"user"`. Could be `"system"` for automated actions |
| `location_id` | UUID (FK -> locations) | Where the event happened, if applicable. Used for location-based access filtering |
| `aggregate_type` | String(100) | Groups events by entity kind. Examples: `"Item"`, `"Location"`, `"User"` |
| `aggregate_id` | UUID | The specific entity instance this event belongs to. Together with `aggregate_type`, this lets you fetch the complete history of any entity |
| `aggregate_version` | Integer | Optional sequence number within an aggregate (not currently enforced) |
| `occurred_at` | DateTime (tz) | When the event happened (business time). Indexed |
| `recorded_at` | DateTime (tz) | When the event was stored (system time) |

### How to Read This Table

To get the full history of an Item:
```sql
SELECT * FROM movement_events
WHERE aggregate_type = 'Item' AND aggregate_id = '<uuid>'
ORDER BY occurred_at ASC;
```
This returns every event in sequence: `ITEM_CREATED`, `ITEM_UPDATED`, `ITEM_DEACTIVATED`, etc.

To see everything a specific user did:
```sql
SELECT * FROM movement_events WHERE actor_id = '<uuid>' ORDER BY occurred_at DESC;
```

To see all activity at a location:
```sql
SELECT * FROM movement_events WHERE location_id = '<uuid>' ORDER BY occurred_at DESC;
```

---

## Event Types

The system does not prescribe a fixed set of events. **You define the events your process needs.** The event store accepts any event type -- it is a generic infrastructure that records facts about any business process.

An event type is simply a string in `SCREAMING_SNAKE_CASE` (enforced by a CHECK constraint: `^[A-Z][A-Z0-9_]*$`). You can create whatever event types make sense for your domain.

### Naming Convention

Event types follow a `{NOUN}_{PAST_TENSE_VERB}` pattern. They always describe something that **already happened** -- they are facts, not commands.

Examples:
- `ORDER_PLACED`, `ORDER_APPROVED`, `ORDER_CANCELLED`
- `BATCH_CREATED`, `CUTTING_COMPLETED`, `QC_PASSED`
- `TICKET_OPENED`, `TICKET_ESCALATED`, `TICKET_RESOLVED`

### How Event Types Are Organized

Event types are registered in a central enum and grouped into categories for UI display. When you design a new process, its event types get added here alongside any others.

For reference, here are the event types that have been defined so far for processes already built on this system:

| Category | Event Types | Process |
|---|---|---|
| **Master Data** | `ITEM_CREATED`, `ITEM_UPDATED`, `ITEM_DEACTIVATED`, `LOCATION_CREATED`, `LOCATION_UPDATED`, `LOCATION_DEACTIVATED`, `USER_CREATED`, `USER_UPDATED`, `USER_DEACTIVATED`, `ROLE_CREATED`, `ROLE_UPDATED`, `ACCESS_GRANTED`, `ACCESS_REVOKED` | Core entity management |
| **RBAC** | `PERMISSION_ASSIGNED`, `PERMISSION_REVOKED`, `USER_ROLE_ASSIGNED`, `USER_ROLE_REVOKED` | Role and permission management |
| **Logistics/Inventory** | `GOODS_DISPATCHED`, `GOODS_RECEIVED`, `QC_ACCEPTED`, `QC_REJECTED`, `STOCK_MOVED`, `STOCK_ADJUSTED`, `STOCK_RESERVED`, `STOCK_RELEASED` | Physical movement of goods |
| **Audit** | `USER_LOGGED_IN`, `API_KEY_CREATED`, `API_KEY_REVOKED` | Auth and security audit trail |
| **Settings** | `COMPANY_SETTINGS_UPDATED` | Company branding and AI configuration |
| **AI** | `AI_CONVERSATION_CREATED`, `AI_CONVERSATION_ARCHIVED` | AI Command Center conversations |

These are not special -- they were defined by analysts and developers for specific processes, using the same mechanism available to any new process. Your process will add its own category and event types to this list.

### How Event Types Are Registered

Core event types are defined in `app/events/types.py` as a Python enum. **Project modules register additional event types** by creating an `event_types.py` file in their module directory and calling `register_module()`:

```python
# app/procurement/event_types.py
from app.events.registry import register_module

PO_CREATED = "PO_CREATED"
PO_CONFIRMED = "PO_CONFIRMED"

register_module(
    module_name="procurement",
    event_types={"PO_CREATED": PO_CREATED, "PO_CONFIRMED": PO_CONFIRMED},
    categories={"procurement": [PO_CREATED, PO_CONFIRMED]},
    payload_schemas={
        PO_CREATED: {
            "required": ["id", "vendor_id", "lines"],
            "optional": ["notes"],
            "fields": {
                "id": {"type": "string", "format": "uuid", "description": "PO ID"},
                "vendor_id": {"type": "string", "format": "uuid", "description": "Vendor ID"},
                "lines": {"type": "array", "description": "PO line items"},
                "notes": {"type": "string", "description": "Optional notes"},
            },
        },
    },
)
```

This registration happens at import time. The framework's auto-discovery system imports all `event_types.py` files at startup, so registered types are available before any request is processed.

The registry (`app/events/registry.py`) provides query functions used throughout the system:
- `get_all_event_types()` — core + registered types
- `is_valid_event_type()` — validates event type before emission
- `get_all_payload_schemas()` — core + registered schemas (used by AI tool generation)
- `get_event_category()` — category lookup for any event type

---

## EventService: The Orchestrator

`EventService` (`app/events/service.py`) is the single entry point for creating events. No code should write to `movement_events` except through this service.

### What `create_event()` Does

```python
event = await event_service.create_event(
    event_type="ITEM_CREATED",
    payload={"id": "...", "sku": "BOLT-M8", "name": "M8 Bolt", ...},
    actor_id=current_user.id,
    aggregate_type="Item",
    aggregate_id="<new-item-uuid>",
)
```

Internally, this method does three things in a single database transaction:

1. **Writes the event** to `movement_events` and flushes (but does not commit).
2. **Fans out to every projection service**, calling `apply_event(event)` on each one. Each projection service inspects the `event_type` and either handles it or ignores it. Projection services also flush but do not commit.
3. **Commits the transaction**. The event row and all projection table changes are committed atomically. If any projection fails, everything rolls back -- the event is never stored without its projections being applied.

### Projection Fan-out

The EventService **auto-discovers** all projection services at runtime. It scans every module directory (`app/*/`) for files named `projection_service.py` or `service.py` that contain classes with an `apply_event()` method. Every event passes through all discovered projection services on every `create_event()` call.

This means **adding a new projection service requires no changes to EventService or any core file**. Just create a file with the right pattern and it's automatically wired in.

For reference, the projection services discovered in the current codebase:

| Projection Service | File | What It Maintains |
|---|---|---|
| `InventoryService` | `inventory/service.py` | `inventory_levels` table |
| `MasterDataProjectionService` | `masterdata/service.py` | `items`, `locations` tables |
| `RBACProjectionService` | `rbac/projection_service.py` | `roles`, `role_permissions`, `user_roles` |
| `UserProjectionService` | `users/projection_service.py` | `users` table |
| `SettingsProjectionService` | `settings/projection_service.py` | `company_settings` table |
| `UsageProjectionService` | `usage/projection_service.py` | `daily_usage` table (billing metering) |
| `AIConversationProjectionService` | `ai/projection_service.py` | `ai_conversations` table |
| `APIKeyProjectionService` | `auth/projection_service.py` | `api_keys` table |

### Idempotency

Duplicate prevention works at two levels:

1. **Event level**: If an `idempotency_key` is provided and already exists, the API returns the existing event without creating a new one. This is checked in the router before calling `create_event()`.
2. **Projection level**: Each projection handler checks for existing records before inserting (e.g., "does a role with this ID already exist?"). This makes projections safe to replay.

---

## Projection Services: The Pattern

Each process you design gets its own projection service. Every projection service follows the exact same structure. Understanding the pattern means you can design one for any process.

### Structure

```python
class SomeProjectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_event(self, event: MovementEvent) -> None:
        payload = event.payload

        if event.event_type == EventType.SOMETHING_CREATED.value:
            await self._create_something(payload, event)
        elif event.event_type == EventType.SOMETHING_UPDATED.value:
            await self._update_something(payload, event)
        # ... more event types ...

        await self.db.flush()  # flush, never commit

    async def _create_something(self, payload: dict, event: MovementEvent) -> None:
        # Check if already exists (idempotent)
        existing = await self.db.execute(
            select(Something).where(Something.id == payload["id"])
        )
        if existing.scalar_one_or_none():
            return  # Already processed, skip

        record = Something(
            id=payload["id"],
            name=payload["name"],
            # ... map payload fields to columns ...
        )
        self.db.add(record)
```

### Key rules for projection services

1. **`flush()`, never `commit()`**. The EventService owns the transaction. Projection services only flush to make their changes visible within the transaction.
2. **Always idempotent**. Every handler must check whether the record already exists before inserting. This ensures events can be safely replayed.
3. **Data comes from `event.payload`**. The payload dict is the single source of information. The projection simply maps payload fields to table columns.
4. **Ignore unknown events silently**. If `apply_event()` encounters an event type it does not handle, it does nothing. No error, no log. This is expected behavior.

### Adding a New Projection Service

To add a new projection service for a new domain:

1. Create `app/{module}/projection_service.py` following the pattern above.
2. **That's it.** The EventService auto-discovers any class with an `apply_event(self, event)` method.

No manual registration, no modification of EventService, no imports to add. The new projection will automatically receive every event on the next server restart.

The discovery scans both `projection_service.py` and `service.py` filenames — this accommodates existing naming variations (e.g., `InventoryService` lives in `service.py`, not `projection_service.py`).

---

## How Mutations Work — The Single Emit Endpoint

There is exactly one write endpoint for the entire API:

```
POST /api/v1/events/emit
```

Domain routers (items, locations, users, rbac) are **GET-only**. They have no POST/PATCH/PUT/DELETE endpoints. All state changes — creating items, updating users, assigning roles — go through the single emit endpoint.

The frontend calls this endpoint directly:

```typescript
const createMutation = useMutation({
  mutationFn: (data: FormData) => {
    const id = crypto.randomUUID();
    return eventsApi.emit({
      event_type: "ITEM_CREATED",
      aggregate_type: "Item",
      aggregate_id: id,
      payload: { id, ...data },
    });
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["items"] }),
});
```

The emit endpoint checks the user's permission for the specific event type (`events:{EVENT_TYPE}:emit`) before proceeding. Validation logic (like SKU uniqueness checks) lives in the projection services, not in router endpoints.

Read endpoints (list, get by ID, search) query projection tables directly -- they never touch the event store.

---

## Permissions and RBAC

Permissions are wired directly to event types. The pattern is `events:{EVENT_TYPE}:emit`.

For example, to emit a `GOODS_RECEIVED` event, a user needs the permission `events:GOODS_RECEIVED:emit`. There are also wildcard permissions: `events:*:emit` (can emit any event) and `admin:*:*` (full system access).

The emit endpoint checks permissions using FastAPI dependency injection. The `require_event_permission` dependency extracts the event type from the request body and checks if the current user has the corresponding permission.

RBAC itself is event-sourced: `ROLE_CREATED`, `PERMISSION_ASSIGNED`, `USER_ROLE_ASSIGNED`, etc. are all events in the store, meaning the complete history of who was granted what permission and when is preserved.

---

## The Event Payload

The `payload` JSONB field is the most important part of the event. Its structure depends on the event type. Here are representative examples:

### Entity Creation (e.g., `ITEM_CREATED`)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "sku": "BOLT-M8-SS",
  "name": "M8 Stainless Steel Bolt",
  "category": "fasteners",
  "unit_of_measure": "EA",
  "reorder_point": 100,
  "reorder_quantity": 500
}
```
The `id` field is generated by the API endpoint before emitting the event. The projection service uses it as the primary key for the derived record.

### Entity Update (e.g., `ITEM_UPDATED`)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "M8 Stainless Steel Hex Bolt",
  "reorder_point": 200
}
```
Only the `id` and the changed fields are included. The projection service applies a partial update.

### Quantity Events (e.g., `GOODS_RECEIVED`)
```json
{
  "item_id": "item-uuid",
  "location_id": "location-uuid",
  "quantity": 250,
  "reference": "REF-2024-0042"
}
```

### Relationship Events (e.g., `PERMISSION_ASSIGNED`)
```json
{
  "role_id": "role-uuid",
  "permission_id": "permission-uuid"
}
```

### Design Principle

Put everything the projection service needs into the payload. The payload must be self-contained -- a projection should be able to rebuild its state from the event without querying other tables.

---

## Aggregate Streams

The `aggregate_type` + `aggregate_id` fields group related events into a stream. This is how you reconstruct the full lifecycle of any entity.

For example, an Item's aggregate stream might look like:

| # | event_type | occurred_at | payload (summary) |
|---|---|---|---|
| 1 | `ITEM_CREATED` | 2024-01-15 09:00 | Full item details |
| 2 | `ITEM_UPDATED` | 2024-01-20 14:30 | Changed fields |
| 3 | `ITEM_DEACTIVATED` | 2024-03-01 11:00 | `{id: ...}` |

Querying this stream gives a complete audit trail of the entity's lifecycle, who did what, and when.

---

## Transaction Guarantees

The system enforces **strong consistency** within a single request:

1. The event is written and flushed.
2. All projection services process the event and flush.
3. A single `commit()` makes everything durable.

If any step fails, the entire transaction rolls back. You will never have an event without its projections, or projections without the corresponding event.

This is a deliberate trade-off: strong consistency over eventual consistency. It simplifies reasoning about system state but means all projection logic runs synchronously in the request path.

---

## Cross-Cutting Concerns

### Audit Trail

Audit is built-in. Every state change is an event with `actor_id` and `occurred_at`. No additional audit logging is needed. To answer "who changed this and when?", query the event store by `aggregate_type` and `aggregate_id`.

### Location-Based Access Control

Events optionally carry a `location_id`. When listing events, the system filters by the user's accessible locations (the `user_locations` table). Users only see events at locations they have been granted access to, plus events without a location (like role changes).

### Event Metadata

The `event_metadata` field is for operational context that is not part of the business payload:
- `correlation_id` -- to trace a request across services
- `source` -- which system or integration generated this event
- Any other infrastructure-level information

The system also automatically captures `request_payload_size_bytes` in `event_metadata` for every event emitted via the API. This is used by the usage metering system for billing.

### Event Versioning

The `event_version` field (defaults to 1) allows evolving payload schemas over time. If you change what fields a payload contains, bump the version and handle both versions in your projection service.

### What Is NOT Event-Sourced

Some operational data is written directly to the database, bypassing the event system:
- **Authentication state**: `last_login_at`, `failed_login_attempts`, `locked_until` on the users table
- **Refresh tokens**: JWT token hashes in the `refresh_tokens` table

These are infrastructure concerns (session management, security), not business state. They do not need an audit trail or the ability to be rebuilt from events.

---

## Designing for Multi-Step Processes

The previous sections cover how the event system works. This section covers how to **think about** mapping any real-world business process onto this architecture -- whether that's a procurement cycle, a production line, a sales pipeline, a service workflow, or anything else with sequential steps. The system is a blank canvas; the events, projections, and rules are yours to define.

### The Mental Model: Steps, Events, and Projections

Most business processes are a series of steps. Each step has:

- An **entry point** (something arrives or is initiated -- material received, order placed, request submitted)
- A **process** (something happens -- approval, transformation, inspection, verification)
- An **exit point** (the step completes and hands off to the next -- goods issued, order confirmed, item shipped)
- **Data points** captured at the step (quantities, amounts, approvers, timestamps, pass/fail, reference numbers, notes, etc.)

In this system, **each transition between steps is an event**. The step's entry screen captures data and emits an event. The step's completion screen captures data and emits another event. The events carry all the data points as their payload.

**Example: A production line**
```
Raw Material Store        Cutting Station         Assembly Station        QC Station
    [ENTRY]                 [ENTRY]                 [ENTRY]              [ENTRY]
       |                       |                       |                     |
  RM_RECEIVED            CUTTING_STARTED         ASSEMBLY_STARTED       QC_STARTED
       |                       |                       |                     |
    (store)               (process)               (process)             (inspect)
       |                       |                       |                     |
  RM_ISSUED_TO_PROD      CUTTING_COMPLETED       ASSEMBLY_COMPLETED     QC_COMPLETED
       |                       |                       |                     |
    [EXIT]                  [EXIT]                  [EXIT]               [EXIT]
```

The pattern is the same regardless of the domain. Each step is a pair of events with data points captured at each.

### One Event Can Trigger Side Effects

A single event can cause cascading updates across multiple domains. For example, when a goods receipt event is processed, the projection service could:

1. Create the receipt record
2. Update related order received quantities
3. Update the order status
4. Create additional `GOODS_RECEIVED` events for each line item
5. Apply those events to update inventory levels

All of this happens within the same database transaction.

This pattern is how you connect steps in any process. For example:
- When a `CUTTING_COMPLETED` event is emitted, the projection could update the work order's progress, create `STOCK_MOVED` events for material transfer, and update a throughput report.
- When an approval event is emitted, the projection could auto-generate a downstream creation event.
- When a payment event is emitted, the projection could update the outstanding balance and close the invoice.

The analyst should **identify which events cascade into other events** when designing the process. This is a key part of the PRD: not just "what events exist" but "what does each event trigger."

### How to Handle Status Transitions and Business Rules

The event store records facts -- it does not enforce ordering. Business rules like "you cannot confirm an order that is already cancelled" or "you cannot dispatch without QC approval" are enforced **in the API endpoint**, before the event is emitted.

The pattern:

```
API endpoint receives request to emit ORDER_CONFIRMED
  -> Query the orders projection table
  -> Check: is the current status "DRAFT"?
  -> If not, reject with a 400 error
  -> If yes, emit the ORDER_CONFIRMED event
```

This applies to every process. When designing a process flow, the analyst should define:

1. **The valid status values** for the entity (e.g., `DRAFT`, `CONFIRMED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`)
2. **The allowed transitions** between statuses (which event moves it from which status to which status)
3. **The preconditions** for each transition (what must be true before this event can happen)

This is the state machine for the process. It should be documented explicitly in the PRD so the developer knows exactly what validation logic to write.

### How Locations Map to Your Process

The system has a hierarchical location model: `warehouse -> zone -> bin`. This maps to different process contexts in different ways:

| Process Context | Location Type | Example Code | Example Name |
|---|---|---|---|
| A site or facility | `warehouse` | `FACTORY-1` | Mumbai Factory |
| | `warehouse` | `WH-CENTRAL` | Central Warehouse |
| A functional area | `zone` | `RM-STORE` | Raw Material Store |
| | `zone` | `DISPATCH-BAY` | Dispatch Bay |
| | `zone` | `PICK-ZONE-A` | Picking Zone A |
| A workstation or position | `bin` | `CUT-STN-01` | Cutting Station 1 |
| | `bin` | `PACK-STN-03` | Packing Station 3 |
| A storage slot | `bin` | `RM-STORE-A1` | Raw Material Rack A, Shelf 1 |

Every event carries a `location_id`. This means the system knows **where** each event happened. This enables location-based reporting (activity per area, volume per station) and location-based access control (a supervisor sees only their area's events).

Not every process involves physical locations. For document-centric processes (approvals, invoicing), `location_id` can be left empty -- the event still captures who did what and when.

**Note:** The current location types are constrained to `warehouse`, `zone`, and `bin`. If your process needs additional types (e.g., `production_line`, `workstation`, `counter`), the constraint will need to be extended. The analyst should call this out if needed.

### Defining Your Event Types

You define the event types your process needs. Every step in your process that represents a meaningful transition becomes an event type.

Some event types from other processes may be relevant to yours. For example, if your process involves physical goods arriving at a location, you can use `GOODS_RECEIVED` -- that event type already has projection logic that updates inventory levels. Similarly, `STOCK_MOVED`, `QC_ACCEPTED`, `GOODS_DISPATCHED`, etc. already have inventory and logistics projections wired up.

But this is not a constraint. If none of the existing types fit, define your own. The system is designed to be extended with any event types your process requires. A new event type is just a string and a payload contract -- the system handles it the same way regardless of whether it was the first event type defined or the hundredth.

### Defining Projection Tables (Reports)

Here's the key question: **what do people need to see?**

Projection tables are not predefined. You define them based on what the business needs to see. Every projection table is essentially a report that stays up-to-date in real time as events flow through the system. When designing a process, list the reports/views the business needs and work backward to the projection tables that would power them.

**Examples across different processes:**

| What the Business Needs | Projection Table | Updated By Which Events |
|---|---|---|
| "Where is batch X right now?" | `production_batches` (status, current_location, current_stage) | Every stage transition event |
| "What's the WIP at each station?" | `station_wip` (station_id, item_id, quantity) | Step entry/exit events |
| "How many units did cutting produce today?" | `station_throughput` (station_id, date, quantity_in, quantity_out, yield_pct) | Step completion events |
| "What's our order fulfillment rate?" | `fulfillment_summary` (period, orders_placed, orders_shipped, on_time_pct) | Order lifecycle events |
| "What raw materials have been consumed?" | `inventory_levels` (item, location, qty on hand) | `STOCK_MOVED`, `STOCK_ADJUSTED` events |
| "What's the QC pass/fail rate?" | `qc_summary` (item_id, period, passed, failed, fail_rate) | `QC_ACCEPTED`, `QC_REJECTED` events |
| "Show me the full history of order X" | Not a projection -- query `movement_events` by `aggregate_type` + `aggregate_id` | Automatic (all events are stored) |

The analyst should document each projection with:
1. **What question it answers** (in plain language)
2. **What columns/fields it needs** (to answer that question)
3. **Which events update it** (the link between events and reports)

This is the most important part of the PRD for the development team. Getting this wrong means either missing reports or building projections that don't get updated by the right events.

### Connecting Separate Entities in a Process Chain

Most processes involve multiple entity types. These are separate aggregates with their own event streams.

The way they connect is **through payload fields**:

**Example: A production process**
1. `PRODUCTION_ORDER_CREATED` creates the production order aggregate.
2. `BATCH_CREATED` creates a batch aggregate, with `production_order_id` in its payload.
3. `STOCK_MOVED` moves raw materials, with `batch_id` in its payload.
4. Step events update the batch status and may trigger further `STOCK_MOVED` events.

**Example: A sales process**
1. `SO_CREATED` creates the sales order aggregate.
2. `SO_PICKED` references the `sales_order_id` and triggers `STOCK_RESERVED` events.
3. `SO_SHIPPED` references the `sales_order_id` and triggers `GOODS_DISPATCHED` events.

The pattern is always the same. When designing a process flow, identify:
- **What are the distinct aggregates?** (order, shipment, invoice, batch, etc.)
- **What events belong to each aggregate?**
- **How do aggregates reference each other?** (which payload fields link them)

---

## Plugin Architecture & Module Conventions

The system uses **file-convention auto-discovery** so that adding a new module never requires modifying core files. A module is a directory under `app/` that follows these conventions:

### Module File Structure

| File | Required | Purpose | Auto-discovered by |
|------|----------|---------|-------------------|
| `__init__.py` | Yes | Python package marker | — |
| `event_types.py` | If module has events | Calls `register_module()` to register event types, categories, and payload schemas | `discover_event_types()` |
| `models.py` | Yes | SQLAlchemy table definitions | `discover_models()` (for Alembic) |
| `projection_service.py` | If module handles events | Class with `apply_event(self, event)` method | `discover_projection_services()` |
| `service.py` | Optional | Read-only query operations (also discovered for `apply_event()` if present) | `discover_projection_services()` |
| `router.py` | Optional | GET-only FastAPI router (must export a `router` variable) | `discover_routers()` |
| `schemas.py` | Optional | Pydantic response models | — |
| `seed.py` | Optional | Async `seed(db)` function for module-specific seed data | `discover_seed_functions()` |

### Core vs. Project Modules

The framework manifest (`phlo.json`) distinguishes:

- **Core modules**: `auth`, `core`, `events`, `rbac`, `users`, `settings`, `usage`, `ai` — provided by the framework, never modified
- **Starter modules**: `items`, `locations`, `inventory`, `masterdata` — can be customized or removed
- **Project modules**: created per customer (e.g., `boms`, `procurement`, `production`) — fully custom

### Auto-Discovery System

Two core files drive the plugin architecture:

- **`app/events/registry.py`** — Holds registered event types, categories, payload schemas, and aggregate maps. Modules register via `register_module()`.
- **`app/events/discovery.py`** — Scans `app/*/` directories for convention files. All discovery results are cached per-process (scan happens once, not per request).

At startup:
1. `discover_event_types()` imports all `app/*/event_types.py` files, triggering `register_module()` calls
2. `discover_routers()` finds all `app/*/router.py` files and registers their routers
3. On first event creation, `discover_projection_services()` finds all projection classes

### How to Add a New Feature (End to End)

1. Create `app/{module}/` directory with `__init__.py`
2. Define event types in `app/{module}/event_types.py` using `register_module()`
3. Create models in `app/{module}/models.py`
4. Create projection service in `app/{module}/projection_service.py`
5. Create read-only router in `app/{module}/router.py` (optional)
6. Create schemas in `app/{module}/schemas.py` (optional)
7. Create seed data in `app/{module}/seed.py` (optional)
8. Create ontology in `docs/ontology/{module}.md` with frontmatter permissions (optional, for AI)
9. Generate Alembic migration: `docker compose exec api alembic revision --autogenerate -m "Add {module} tables"`
10. Run: `make migrate && make seed`

**No core files need to be modified.** Everything is auto-discovered.

---

## Infrastructure Summary

| Component | Technology | Role |
|---|---|---|
| Event Store | PostgreSQL 16 (JSONB) | Single `movement_events` table. Append-only |
| Projection Tables | PostgreSQL 16 | Standard relational tables derived from events |
| API | FastAPI (async) | Validates input, emits events, queries projections |
| ORM | SQLAlchemy (async) | Models, queries, transaction management |
| Auth | JWT (OAuth2) | Access tokens + refresh token rotation |
| Migrations | Alembic | Schema versioning for all tables |
| Event Registry | Python module | `app/events/registry.py` — registered event types + payload schemas |
| Auto-Discovery | Python module | `app/events/discovery.py` — finds projections, routers, models, seeds |
| AI Command Center | Claude Agent SDK | Natural language interface using auto-generated tools |
| Usage Metering | PostgreSQL | `daily_usage` table — event counts and payload sizes |
