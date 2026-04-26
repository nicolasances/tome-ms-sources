# Tome Sources API

This service has the responsibility of managing the **Sources of Knowledge** for Tome. 

## General Capabilites

This service provides the following capabilities, reflected through its endpoints: 

- **Ingestion** - it ingests the information contained in the *Sources* into Google Storage, for simplified later processing. 
- **Targeted Processing** - it processes the information to *create knowledge in Tome*. This processing is targeted and guided by the consumer. It can be: 
    - **Language-driven** - it will take the data source and use it as a souce for creating training material for the Language Learning section of Tome. 

## Currently supported Sources

### Google Docs
To support Google Docs, the user must **manually share a document (or folder) with the GCP Service Account of this service**. <br>
The Tome app will guide the user through this process. 



