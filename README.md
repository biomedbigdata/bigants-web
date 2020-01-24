# 1. Getting Started
BiCoN-web comes in an easy to use `docker-compose` format.

To deploy BiCoN-web in a production environment, please ensure you have a working docker (and docker-compose) environment running. 
You find a manual for install docker on your operating system [here](https://docs.docker.com/install/).

Once docker is installed and running, execute the following commands:

## Running BiCoN-web for the first time
To install BiCoN-web (running it for the first time) follow these steps:
```shell script
# First clone this repository and change into the created directory
git clone https://github.com/biomedbigdata/BiCoN-web.git && cd BiCoN-web

# Deploy and build the containers
docker-compose up -d --build

# Apply migrations to the database (make sure the containers are up an running, else you will get an error)
docker-compose exec web python manage.py migrate --noinput 

# Collect all the static files
docker-compose exec web python manage.py collectstatic --no-input

```

## Start and stop BiCoN-web
All the important files are stored inside persistant volumes and are available even after restarting the containers

**Start service**

Navigate to the repository folder
```shell script
docker-compose up -d
```

**Stop service**

Navigate to the repository folder

```shell script
docker-compose down
```

## Managing volumes and data
The docker containers store their data in three volumes which can be backup or moved when the application needs to 
move to another client.

**Backing up volumes**

**Deleting volumes / all data**

CAREFULL, docker does not ask for confirmation when deleting volumes!
```shell script
docker-compose down --volumes
```