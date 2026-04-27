from typing import List, Optional

from bson import ObjectId

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

    def find_source_by_id(self, source_id: str) -> Optional[Source]:
        """Return the Source with the given ObjectId, or None if not found."""
        result = self.db[self.COLLECTION].find_one({"_id": ObjectId(source_id)})
        if not result:
            return None
        return Source.from_bson(result)

    def update_last_extracted_at(self, source_id: str, timestamp: str) -> None:
        """Set lastExtractedAt to *timestamp* on the source identified by *source_id*."""
        self.db[self.COLLECTION].update_one(
            {"_id": ObjectId(source_id)},
            {"$set": {"lastExtractedAt": timestamp}},
        )
