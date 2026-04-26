from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.model import ExecutionContext, UserContext

from model.source import Source
from store.sources_store import SourcesStore


@toto_delegate
async def post_source(request: Request, user_context: UserContext, exec_context: ExecutionContext):
    req = await parse_request(request, exec_context.config)
    if isinstance(req, JSONResponse):
        return req
    return await do(req, user_context, exec_context)


async def parse_request(request: Request, config) -> "PostSourceRequest | JSONResponse":
    try:
        body = await request.json()
    except Exception:
        body = {}

    source_type = body.get("type")
    language = body.get("language")
    name = body.get("name")
    resource_id = body.get("resourceId")

    if not source_type:
        return JSONResponse(content={"message": "Missing required field: type"}, status_code=400)
    if not language:
        return JSONResponse(content={"message": "Missing required field: language"}, status_code=400)
    if not name:
        return JSONResponse(content={"message": "Missing required field: name"}, status_code=400)
    if not resource_id:
        return JSONResponse(content={"message": "Missing required field: resourceId"}, status_code=400)

    if source_type not in config.supported_types:
        return JSONResponse(content={"message": f"Unsupported type: {source_type}"}, status_code=400)
    if language not in config.supported_languages:
        return JSONResponse(content={"message": f"Unsupported language: {language}"}, status_code=400)
    if "/" in resource_id:
        return JSONResponse(content={"message": "resourceId must not contain '/': provide the document ID, not the full URL"}, status_code=400)

    return PostSourceRequest(type=source_type, language=language, name=name, resource_id=resource_id)


async def do(req: "PostSourceRequest", user_context: UserContext, exec_context: ExecutionContext) -> JSONResponse:
    config = exec_context.config

    source = Source(
        type=req.type,
        language=req.language,
        name=req.name,
        resource_id=req.resource_id,
        user_id=user_context.email,
        created_at=datetime.now(timezone.utc).isoformat(),
        last_extracted_at=None,
    )

    store = SourcesStore(config)
    source_id = store.save_source(source)

    return JSONResponse(content={"id": source_id}, status_code=201)


class PostSourceRequest(BaseModel):
    type: str
    language: str
    name: str
    resource_id: str
