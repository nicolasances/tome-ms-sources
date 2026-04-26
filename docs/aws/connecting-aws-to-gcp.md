# Connecting AWS and GCP
In order to be able to have workloads on AWS be able to access resources on GCP, I needed to allow my AWS services to authenticate to GCP. 

> *An example is to have an AWS-deployed service be able to connect to GCP Cloud Storage. <br>*
*Concretely I used that to have an AWS-deployed ML model to be able to access training data on GCP CS.*

## For ECS Deployments
This section explains how I connected an ECS-deployed service to GCP.

*Against the latest best practices** (which consists in configuring Federated Workload Identity), I went the easy way and used the good old `GOOGLE_APPLICATION_CREDENTIALS`.

To do that I needed to do the following: 
1. **Create a new Service Account on GCP** with limited permissions and **generate a JSON key file**. 
2. Copy the content of the key file into a **Github Secret**.
3. At **container-creation time** (not build-time), **create a file containing the JSON key**, mount it and refer to it in the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

To do the first part, I: 
* manually created a new role and a new Service Account with that role on GCP, 
* exported a key as a JSON file, 
* created a new Terraform variable on `toto-aws-terra` containing the base64-encoded JSON copied from the file

To do the second part, I just modified the Terraform file that creates the microservice repo to add a new secret (creatively called `GOOGLE_APPLICATION_CREDENTIALS`) in the repo of the microservice.

To do the last part I did the following. <br>
I added to the ECS Task Definition of the service the following enviornment variables:
```
environment: [
    ... ,
    {
        name = "GOOGLE_APPLICATION_CREDENTIALS", 
        value = "/secrets/gcp_cred.json"
    }, 
    {
        name  = "GCP_SERVICE_ACCOUNT_KEY",
        value = var.gcp_service_account_key
    }
]
```

Then, I added the following, always to the ECS Task Definition: 
```
entryPoint = [ "sh", "-c", "echo \"$GCP_SERVICE_ACCOUNT_KEY\" | base64 -d > /secrets/gcp_cred.json && exec gunicorn --bind 0.0.0.0:8080 app:app --enable-stdio-inheritance --timeout 3600 --workers=2" ]
mountPoints = [
    {
        sourceVolume = "gcp_credentials_volume"
        containerPath = "/secrets"
        readOnly = false
    }
]
```
The first part modifies the Docker entrypoint to add the copying of the content of the GCP Service Account Key to a credentials file, under the "secrets" folder.<br>
The second part add a mount to a volume. 

Finally, we need to define the volume: 
```
resource "aws_ecs_task_definition" "service_task_def" {
  container_definitions = jsonencode([
    ...
  ])

  volume {
    name = "gcp_credentials_volume"
  }
}
```

So now, the `toto-aws-terra/terraform/repo-toto-python-ms-template.tf.tocopy` file has an added Github Secret: 
```
########################################################
# 1.10 Google Application Credentials
#      For services that need to access GCP Toto Infra 
########################################################
resource "github_actions_environment_secret" "toto_ml_supito_secret_gcp_service_account_key" {
    repository = data.github_repository.service_gh_repo.name
    environment = var.toto_environment
    secret_name = "GOOGLE_APPLICATION_CREDENTIALS"
    plaintext_value = base64encode(var.gcp_service_account_key)
}
```