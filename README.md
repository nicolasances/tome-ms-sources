# Tome Sources API

This service has the responsibility of managing the **Sources of Knowledge** for Tome. 

## Table of Contents

- [General Capabilities](#general-capabilites)
- [Currently Supported Sources](#currently-supported-sources)
  - [Google Docs](#google-docs)
- [Dev Utilities](#dev-utilities)
  - [test/test_google_doc_fetcher.py](#testtestgoogleocfetcherpy)

## General Capabilites

This service provides the following capabilities, reflected through its endpoints: 

- **Ingestion** - it ingests the information contained in the *Sources* into Google Storage, for simplified later processing. 
- **Targeted Processing** - it processes the information to *create knowledge in Tome*. This processing is targeted and guided by the consumer. It can be: 
    - **Language-driven** - it will take the data source and use it as a souce for creating training material for the Language Learning section of Tome. 

## Currently supported Sources

### Google Docs
To support Google Docs, the user must **manually share a document (or folder) with the GCP Service Account of this service**. <br>
The Tome app will guide the user through this process. 


## Dev Utilities

### test/test_google_doc_fetcher.py

A small script to manually test the `GoogleDocFetcher` against a real Google Doc.

**Prerequisites**

- Google Application Default Credentials must be configured. Run the following once to set them up locally:
  ```bash
  gcloud auth application-default login
  ```
- The target document must be shared with your authenticated account (or service account).

**Usage**

```bash
python test/test_google_doc_fetcher.py <google_doc_id>
```

The `<google_doc_id>` is the long alphanumeric string in the document URL:

```
https://docs.google.com/document/d/<DOCUMENT_ID>/edit
```

The script prints the plain-text content extracted from the document, followed by the total character count.
