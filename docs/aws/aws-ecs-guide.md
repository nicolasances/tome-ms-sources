# Toto Microservice for AWS ECS

This Guide will help you use this template project to create, build and deploy a Toto Microservice on AWS ECS Infrastructure (Toto Environment).

In general, you can find a general description of Toto AWS Architecture in the [Toto Documentation Repository](https://github.com/nicolasances/toto). 

Additional guides and notes:
 * [How to Connect AWS to GCP](./connecting-aws-to-gcp.md), documents how we make sure we can connect from AWS to GCP, allowing services running on AWS to consume resources (like GCS) on GCP.

## 1. Create a Github Repository
Before doing anything, you need to create a Github Repository for your Microservice.

## 2. Create a Workspace Repository
Once that is done, create a Terraform Workspace on https://app.terraform.io. <br>
A Toto Microservice will need **at least two workspaces**: 
* a *dev* workspace
* a *prod* workspace

The workspaces **must follow the following naming convention**: `<name of the microservice>-<env>`. <br>
*For example the following names are valid*: for a Microservice called `toto-ms-expenses`, the two workspaces should be called `toto-ms-expenses-dev` and `toto-ms-expenses-prod`.

## 3. Update the Core Infrastructure Terraform Modules
You will now have to update the project `toto-aws-terra` which is the repo containing all the infrastructure definition for Toto on AWS. 

You will have to do the following steps: 

1. Copy the file under `aws/toto-aws-terra/terraform` called `repo-toto-python-ms-template.tf.tocopy` to the `terraform` folder of `toto-aws-terra`.

2. Rename the file with the following naming convention: `repo-<name of your microservice>.tf`. <br>
*For example, if you microservice is called `toto-ms-expenses` the file will have to be renamed `repo-toto-ms-expenses.tf`*.

3. Open that file an change the following resources:
    * Every resource's name should be changed by putting a custom prefix. Use your microservice name as a custom prefix. <br>
    *E.g. If your service is called toto-ms-expenses, resource 'ecr_private_repo' should be renamed to 'toto_ms_expenses_ecr_private_repo'*
    * Resource `service_gh_repo` should have the full name of the Github Repo that you have created earlier. <br>
    **ATTENTION**: once you have changed the name of the resource `service_gh_repo` you need to propagate that change to all the resources that were referencing it. They all have a line referencing `data.github_repository.service_gh_repo.name`.
    * Resource `ecr_repo` should have the name of the microservice
    * Resource `tf_workspace_ghsecret` should have the "plaintext value" to use the name of the microservice instead of the name of the template microservice.
    * Resource `ecr_repo` has a plaintext value referring to resource `ecr_private_repo`. Once you have changed the name of the resource, you need to change the reference in the plaintext value.

4. In the github worfklow, change the name of the Environment Variable called `SERVICE_NAME` to the name of the microservice. <br>
The default is `toto-python-ms-template` and if your service is called `toto-ms-invoices` use the latter instead.

5. **Commit and Push**. <br>
That will trigger the Terraform plan and apply and will update your Microservice's Github Repo with the needed Secrets. 

Once that is done, you can safely **delete** the folder `toto-aws-terra` in your project. 

## 4. Delete any non-needed Terraform Folder
The folder under `aws/terraform` contains all the needed Terraform resources to setup this Microservice on AWS. <br>
All other folders that contain Terraform files can be deleted

## 5. Update the Terraform resources & move the Terraform folder
The following files and resources need to be updated: 
* `aws/terraform/locals.tf`: you should change the `toto_microservice_name` value to your Microservice name

Move the `terraform` folder on level up (under the project's root).

## 6. Move the Github Workflows
The Github Workflows are under `aws/.github/workflows`. <br>
You need to move the whole `.github` folder up one level. 

## 7. Freeze
Run a `pip freeze > requirements.txt` to generate the requirements file. 

## 8. Commit and Push
Commit and Push in the target environment, to run the Github Action.
