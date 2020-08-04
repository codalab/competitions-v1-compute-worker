FROM ubuntu:18.04
 
#####
# Install docker 19.03
#####
 
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
RUN add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
   $(lsb_release -cs) \
   stable"
RUN apt-get update && apt-get install -y \
   docker-ce=5:19.03.12~3-0~ubuntu-bionic \
   docker-ce-cli=5:19.03.12~3-0~ubuntu-bionic \
   containerd.io=1.2.13-2
 
#####
# Install nvidia-container-toolkit
#####
 
RUN curl -fsSL https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
RUN curl -fsSL https://nvidia.github.io/nvidia-docker/ubuntu18.04/nvidia-docker.list \
    | tee /etc/apt/sources.list.d/nvidia-docker.list
 
RUN apt-get update && apt-get install -y nvidia-container-toolkit
 
#####
# Install entr which is a file watching library
#####
RUN apt-get install -y entr

#####
# Install python 3.8 and pip3
#####

RUN apt-get install -y python3.8 python3-pip

# Move into our worker directory, so we're not in /
WORKDIR /worker/
 
# Install Python stuff we need to listen to the queue
COPY requirements.txt /worker/requirements.txt
RUN pip3 install -r requirements.txt
 
# Copy our actual code
COPY *.py /worker/
COPY detailed_result_put.sh /worker/
 
# Run it
CMD celery -A worker worker -l info -Q compute-worker -n compute-worker%h -Ofast -Ofair --concurrency=1
