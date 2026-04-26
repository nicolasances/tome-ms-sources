from fastapi import Request
from pymongo import MongoClient
from totoms.TotoDelegateDecorator import toto_delegate
from totoms.model import ExecutionContext, UserContext

from store.sources_store import SourcesStore


@toto_delegate
async def get_sources(request: Request, user_context: UserContext, exec_context: ExecutionContext):
    config = exec_context.config
    language = request.query_params.get("language")

    client = MongoClient(
        host=config.mongo_host,
        username=config.mongo_user,
        password=config.mongo_pwd,
    )
    db = client[config.get_db_name()]

    store = SourcesStore(db, config)
    sources = store.find_sources_by_user(user_context.email, language=language)

    return {"sources": [s.to_response() for s in sources]}
