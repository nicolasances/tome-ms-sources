
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth import default as google_auth_default


class GoogleDocFetcher:
    """Fetches plain-text content from a Google Doc using the Google Docs API."""

    def fetch(self, source: dict) -> str:
        """
        Fetch plain-text content from the Google Doc identified by source['resourceId'].

        Args:
            source: The full stored source document, including 'resourceId'.

        Returns:
            A plain-text string of the document's content, or an empty string if
            the document has no textual content.

        Raises:
            Exception: On a permission error (403) or any other Google API error.
        """
        resource_id = source["resourceId"]

        credentials, _ = google_auth_default(scopes=["https://www.googleapis.com/auth/documents.readonly"])
        
        service = build("docs", "v1", credentials=credentials)
        
        sa_email = getattr(credentials, "service_account_email", None)
        print(f"Using credentials for: {sa_email}")

        try:
            result = service.documents().get(documentId=resource_id).execute()
        except HttpError as e:
            
            if e.resp.status == 403:
                print(f"{e.resp.status} error: {e._get_reason()}")
                raise Exception(
                    f"Permission denied accessing Google Doc '{resource_id}'. "
                    "Please share the document with the service account."
                ) from e
                
            raise Exception(
                f"Google Docs API error while accessing document '{resource_id}': {e}"
            ) from e

        body_content = result.get("body", {}).get("content", [])
        texts = []
        for element in body_content:
            self._extract_structural_element(element, texts)

        return "\n".join(t for t in texts if t)

    def _extract_structural_element(self, element: dict, texts: list) -> None:
        """Recursively extract text from a structural element."""
        if "paragraph" in element:
            text = self._extract_paragraph_text(element["paragraph"])
            if text:
                texts.append(text)
        elif "table" in element:
            self._extract_table_text(element["table"], texts)
        elif "tableOfContents" in element:
            for toc_element in element["tableOfContents"].get("content", []):
                self._extract_structural_element(toc_element, texts)

    def _extract_paragraph_text(self, paragraph: dict) -> str:
        """Extract plain text from a paragraph element."""
        parts = []
        for elem in paragraph.get("elements", []):
            text_run = elem.get("textRun")
            if text_run:
                content = text_run.get("content", "")
                parts.append(content)
        return "".join(parts).rstrip("\n")

    def _extract_table_text(self, table: dict, texts: list) -> None:
        """Extract plain text from all cells in a table."""
        for row in table.get("tableRows", []):
            for cell in row.get("tableCells", []):
                for element in cell.get("content", []):
                    self._extract_structural_element(element, texts)
