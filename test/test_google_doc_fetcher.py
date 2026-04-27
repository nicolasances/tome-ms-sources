"""
Test utility for GoogleDocFetcher.

Usage:
    python test/test_google_doc_fetcher.py <google_doc_id>

The Google Doc ID is the long alphanumeric string in the document's URL:
    https://docs.google.com/document/d/<DOCUMENT_ID>/edit

Requirements:
    - Google Application Default Credentials must be configured.
      Run `gcloud auth application-default login` to set them up locally.
    - The document must be shared with the authenticated account or service account.
"""

import sys
import os

# Allow importing from the project root regardless of where the script is run from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dlg.fetchers.google_doc_fetcher import GoogleDocFetcher


def main():
    if len(sys.argv) < 2:
        print("Usage: python test/test_google_doc_fetcher.py <google_doc_id>")
        print()
        print("  <google_doc_id>  The document ID from the Google Doc URL:")
        print("  https://docs.google.com/document/d/<DOCUMENT_ID>/edit")
        sys.exit(1)

    doc_id = sys.argv[1]

    print(f"Fetching Google Doc: {doc_id}")
    print("-" * 60)

    fetcher = GoogleDocFetcher()

    # GoogleDocFetcher.fetch() expects a source dict with a 'resourceId' key,
    # matching the structure of a stored source document in MongoDB.
    source = {"resourceId": doc_id}

    try:
        content = fetcher.fetch(source)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    if not content:
        print("(Document is empty or contains no text)")
    else:
        print(content)

    print("-" * 60)
    print(f"Done. {len(content)} characters fetched.")


if __name__ == "__main__":
    main()
