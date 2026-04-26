# Guide to configuring this service on GCP

## 1. Execute the preparation steps
Make sure you have executed the steps that clone the repo. 

## 2. Github Actions
* Elevate the folder `gcp/.github/workflows` to the root of your microservice
* In the `release-*.yml` files, make sure that you set the correct: 
    * `SERVICE_NAME` ENV var
    * `SERVICE_VERSION` ENV var

## 3. Terraform on GCP
* Copy the file `gcp/terraform/toto-ms-xxx.tf` in the project `toto-terra`
* Make sure you change all references to `toto-ms-xxx` and use your *service name** instead. 
* Commit and push, that will trigger the Terraform apply.

At this point you have a working service locally and terraform has created the necessary infrastructure and github secrets. 

## 4. Config file
* In the class `Config` make sure to specify GCP as the cloud provider

```
@singleton
class Config(TotoConfig): 
    
    def __init__(self):
        super().__init__(cloud_provider=CloudProvider.GCP)
        
        self.logger.log("INIT", "Configuration loaded!")
```

## 5. Push
Commit your service and push it to Github. 