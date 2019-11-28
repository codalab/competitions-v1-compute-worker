original code and README here (https://github.com/codalab/competitions-v1-compute-worker)

Why do you need ACI-workers ?
=======

Original codalab's workers use local dockers on provisioned machines.
 These machines sometimes have to use GPU like Tesla k80 or others.
 In the clouds VMs with such cool parameters are expensive. 
 If you want to have a scalable system you have to manage these machines 
 (for instance, with Kubernetes), but it could be pretty difficult. 
 That's why we are using ACI - Azure Container Instances (https://azure.microsoft.com/en-us/services/container-instances/)
 This is Azure service that give us a possibility to launch our serverless docker in the Cloud.
  You don't have to worry about a difficult infrastructure or scalability.   

Deploy
=======

## Configs

```
 ───deploy
│   ├── configs
│   │   ├── afs.cred
│   │   ├── afs_creds.yml
│   │   ├── azure_creds
│   │   ├── env_config

```



1. At first, you need to create Azure Resource Group and get `azure_creds` for this group.
With this file your aci-codalab-worker will be able to launch ACI-containers
 (we use https://github.com/igormusinov/cloud-hunky library inside the aci-codalab-worker's container ). 

`azure_creds`
```
{
  "clientId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXX",
  "clientSecret": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
  "subscriptionId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
  "tenantId": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
  "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
  "resourceManagerEndpointUrl": "https://management.azure.com/",
  "activeDirectoryGraphResourceId": "https://graph.windows.net/",
  "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
  "galleryEndpointUrl": "https://gallery.azure.com/",
  "managementEndpointUrl": "https://management.core.windows.net/"
}
```

2. You need the Azure File Storage (https://azure.microsoft.com/en-us/services/storage/files/) 
for mounting your data into the containers.

`afs.cred`
```
username=<name of your File Storage account>
password=<key>
```

`afs_creds.yml`
```
AFS_NAME: "name of your File Storage account"
AFS_KEY: "key"
AFS_SHARE: "your share"
AZURE_SECRET: "(optional)"
```

3. Create `env_config` for your aci-codalab-worker.

`env_config`
```
# For ACI-container management (cloud-hunky)
AZURE_AUTH_LOCATION=/root/.azure/azure_creds

# For celery.
WORKER=celerymain
WORKER_CONCURRENCY=1

# For local/ACI launch
ACI_PRED=True
ACI_SCORE=True

# Logging config
LOG_CFG=/log/logging.yaml

# This is the URL you get from the Worker Queues Management page on Codalab
MAIN_BROKER_URL=<main virtual host>
BROKER_URL=<additional virtual host> (when codalab creates a new queue - it creates a new virtual host)

# Specify when use alternative queues
MAIN_BROKER_LOGIN=<your / login>
MAIN_BROKER_PASS=<your / pass>

# The temporary directory for submissions to do their work in
# Don't forget specify this path in docker mount
SUBMISSION_TEMP_DIR=/tmp/codalab

# Don't create this env
#BROKER_USE_SSL=True

# Docker Registry creds (Optional). For ACI's start time reduction
IMAGE_REGISTRY_SERVER=''
IMAGE_REGISTRY_USERNAME=''
IMAGE_REGISTRY_PWD=''
```

4. Create directory `deploy/configs` and put these configs there.


### Ansible deploy

1. Set your params in the `deploy/ansible.cfg` and `deploy/hosts.yaml` (username and host).

2. If your rabbitmq broker isn't available from outside the VM,
 you have to make ssh tunnel to you `host`. Don't forget to set right URLs in the `configs/env_file`

3. Run ansible playbooks.

```
cd deploy
make mount
make deploy
```

