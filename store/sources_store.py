from typing import List, Optional

from model.source import Source


class SourcesStore:

    COLLECTION = "sources"

    def __init__(self, db, config):
        self.db = db
        self.config = config

    def save_source(self, source: Source) -> str:
        result = self.db[self.COLLECTION].insert_one(source.to_bson())
        return str(result.inserted_id)

    def find_sources_by_user(self, user_id: str, language: Optional[str] = None) -> List[Source]:
        query = {"userId": user_id}
        if language:
            query["language"] = language
        return [Source.from_bson(doc) for doc in self.db[self.COLLECTION].find(query)]
