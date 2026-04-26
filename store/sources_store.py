from typing import List, Optional

from pymongo import MongoClient

from model.source import Source


class SourcesStore:

    DB_NAME = "tomesources"
    COLLECTION = "sources"

    def __init__(self, config):
        self.config = config

    def _get_collection(self):
        client = MongoClient(
            host=self.config.mongo_host,
            username=self.config.mongo_user,
            password=self.config.mongo_pwd,
        )
        return client[self.DB_NAME][self.COLLECTION]

    def save_source(self, source: Source) -> str:
        collection = self._get_collection()
        result = collection.insert_one(source.to_bson())
        return str(result.inserted_id)

    def find_sources_by_user(self, user_id: str, language: Optional[str] = None) -> List[Source]:
        collection = self._get_collection()
        query = {"userId": user_id}
        if language:
            query["language"] = language
        return [Source.from_bson(doc) for doc in collection.find(query)]
