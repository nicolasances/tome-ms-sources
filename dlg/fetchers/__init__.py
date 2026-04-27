
from dlg.fetchers.google_doc_fetcher import GoogleDocFetcher

# Maps source type → fetcher class. Consumers must instantiate the class before calling fetch().
# Example: FETCHER_REGISTRY[source["type"]]().fetch(source)
FETCHER_REGISTRY = {
    "google_doc": GoogleDocFetcher,
}
