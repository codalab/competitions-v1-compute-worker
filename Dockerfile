#FROM ubuntu:16.04
FROM ubuntu:16.04

RUN apt-get update
RUN apt-get install curl wget -y

# Install a specific version of docker
RUN curl -sSL https://get.docker.com/ | sed 's/docker-ce/docker-ce=18.03.0~ce-0~ubuntu/' | sh

# nvidia-docker jazz
RUN curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | \
  apt-key add -

RUN curl -s -L https://nvidia.github.io/nvidia-docker/$(. /etc/os-release;echo $ID$VERSION_ID)/nvidia-docker.list | \
  tee /etc/apt/sources.list.d/nvidia-docker.list
RUN apt-get update
RUN apt-get install -y nvidia-docker2

# Install entr which is a file watching library
RUN apt-get install entr -y

# Move into our worker directory, so we're not in /
WORKDIR /worker/

# Install Python stuff we need to listen to the queue
#RUN apt-get install python-pip -y
#RUN pip install -U pip

RUN apt-get install -y software-properties-common

RUN add-apt-repository ppa:deadsnakes/ppa && apt-get update && apt-get install -y python3.8-dev python3-pip

# RUN apt-get install -y python3.8-dev python3-pip

COPY requirements.txt /worker/requirements.txt
RUN apt install -y python3.8-distutils && apt remove -y python3-pip && python3.8 -m easy_install pip && python3.8 -m pip install -r requirements.txt

# Copy our actual code
COPY *.py /worker/
COPY detailed_result_put.sh /worker/

# Run it
CMD celery -A worker worker -l info -Q compute-worker -n compute-worker%h -Ofast -Ofair --concurrency=1
