# Coding Standards

This document defines the coding standards and architectural conventions for all microservices in this repository. 

---

## Source Folder Structure

```
.
├── app.py             # Entry point - wires API endpoints and event handlers
├── config/
│   └── config.py      # Service configuration (extends TotoControllerConfig)
├── dlg/               # Delegates - one module per API operation
├── model/             # Model classes - entity definitions
├── store/             # Store classes - ALL database access lives here
├── evt/
│   ├── events.py      # Event type constants
│   ├── handlers/      # Event handler classes
│   └── model/         # Event payload models
├── api/               # Clients for external microservice APIs
└── util/              # Shared utilities
docs/                  # General documentation for the project
└── capabilities/      # Documents that generally describe the core capabilities of the microservice
└── specs/             # Documents that describe detailed functionalities, typically subparts of the capabilities
```

---

## Delegates (`dlg/`)

Each API operation has its own file. Delegates use `@toto_delegate` from `totoms.TotoDelegateDecorator` and should contain two clear steps:

- **`parse_request(request)`** - validates and extracts `request` body/params into a typed request model. Raise `ValidationError` for invalid input.
- **`do(req_model, user_context, exec_context)`** - contains all business logic.

In function-based delegates, keep this same split by using small helper functions in the same module.

Request and response types should be defined as local `pydantic` models near the bottom of the same file. They are usually named `<DelegateName>Request` and `<DelegateName>Response`.

File naming preferences (not always possible, so only when possible): `{verb}_{entity}.py` - e.g. `post_topic.py`, `get_topics.py`, `delete_topic.py`.

```python
# dlg/post_topic.py
from fastapi import Request
from pydantic import BaseModel
from totoms.model import ExecutionContext, UserContext
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.Errors import ValidationError


@toto_delegate
async def post_topic(request: Request, user_context: UserContext, exec_context: ExecutionContext):
    req = parse_request(request)
    return await do(req, user_context, exec_context)


def parse_request(request: Request) -> "PostTopicRequest":
    body = request.json() if callable(getattr(request, "json", None)) else request.body
    name = body.get("name") if body else None
    if not name:
        raise ValidationError(400, "No name provided")
    return PostTopicRequest(name=name)


async def do(req: "PostTopicRequest", user_context: UserContext, exec_context: ExecutionContext) -> "PostTopicResponse":
    config = exec_context.config
    db = await config.get_mongo_db(config.get_db_name())

    store = TopicsStore(db, config)
    topic_id = await store.save_topic(Topic(name=req.name))

    return PostTopicResponse(id=topic_id)


class PostTopicRequest(BaseModel):
    name: str


class PostTopicResponse(BaseModel):
    id: str
```

---

## Store Classes (`store/`)

**All database access is strictly confined to Store classes. No other file may query or write to the database.**

- One store per logical entity/collection, named `{entity}_store.py` - e.g. `topics_store.py`.
- Constructor takes a database instance and the service config.
- Methods always return model objects (using `Model.from_bson()`) rather than raw BSON documents.

```python
# store/topics_store.py
from bson import ObjectId


class TopicsStore:

    def __init__(self, db, config):
        self.db = db
        self.config = config
        self.topics_collection = "topics"

    async def find_topic_by_id(self, topic_id: str) -> "Topic | None":
        result = await self.db[self.topics_collection].find_one({"_id": ObjectId(topic_id)})
        if not result:
            return None
        return Topic.from_bson(result)

    async def save_topic(self, topic: "Topic") -> str:
        result = await self.db[self.topics_collection].insert_one(topic.to_bson())
        return str(result.inserted_id)
```

---

## Model Classes (`model/`)

One file per entity, named after the entity in snake_case - e.g. `topic.py`.

Every model class must implement:

- **`@staticmethod from_bson(data: dict) -> Entity`** - converts a raw MongoDB document into a model instance.
- **`to_bson() -> dict`** - converts the model instance into a plain object suitable for MongoDB storage.

---

## Event Handlers (`evt/handlers/`)

Each event type has its own handler file, named `on_<event_name>.py` - e.g. `on_practice_finished.py`.

- Handlers extend `TotoMessageHandler` from `totoms`.
- They declare the `handled_message_type` attribute to identify which events they process.
- The main method is `async def on_message(self, msg: TotoMessage) -> ProcessingResponse`.
- Business logic follows the same pattern as delegates: use a Store for any DB access.

```python
# evt/handlers/on_practice_finished.py
from totoms.TotoMessageHandler import TotoMessageHandler
from totoms.model import ProcessingResponse, TotoMessage


class OnPracticeFinished(TotoMessageHandler):

    handled_message_type = "practiceFinished"

    async def on_message(self, msg: TotoMessage) -> ProcessingResponse:
        config = self.config
        db = await config.get_mongo_db(config.get_db_name())

        await TopicsStore(db, config).update_topic_last_practice(...)

        return ProcessingResponse(status="processed", response_payload="...")
```

Event type constants are defined in `evt/events.py` as a plain exported dictionary:

```python
EVENTS = {
    "topic_created": "topicCreated",
    "topic_deleted": "topicDeleted",
}
```

---

## External API Clients (`api/`)

When calling another microservice, wrap all HTTP calls in a dedicated client class named `{service}_api.py` - e.g. `flashcards_api.py`. No raw HTTP calls outside of these classes.

---

## Documentation
- The README mostly contains a general description of the service and a table of contents that links to other relevant documentation in the `docs/` folder.
- All other documentation is in the `docs/` folder, in the right subfolder, according to the type of document: a Capability description document or a Spec for a feature.