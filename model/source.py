from typing import Optional


class Source:

    def __init__(
        self,
        type: str,
        language: str,
        name: str,
        resource_id: str,
        user_id: str,
        created_at: str,
        last_extracted_at: Optional[str] = None,
        id: Optional[str] = None,
    ):
        self.id = id
        self.type = type
        self.language = language
        self.name = name
        self.resource_id = resource_id
        self.user_id = user_id
        self.created_at = created_at
        self.last_extracted_at = last_extracted_at

    @staticmethod
    def from_bson(data: dict) -> "Source":
        return Source(
            id=str(data["_id"]),
            type=data["type"],
            language=data["language"],
            name=data["name"],
            resource_id=data["resourceId"],
            user_id=data["userId"],
            created_at=data["createdAt"],
            last_extracted_at=data.get("lastExtractedAt"),
        )

    def to_bson(self) -> dict:
        return {
            "type": self.type,
            "language": self.language,
            "name": self.name,
            "resourceId": self.resource_id,
            "userId": self.user_id,
            "createdAt": self.created_at,
            "lastExtractedAt": self.last_extracted_at,
        }

    def to_response(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "language": self.language,
            "name": self.name,
            "resourceId": self.resource_id,
            "createdAt": self.created_at,
            "lastExtractedAt": self.last_extracted_at,
        }
