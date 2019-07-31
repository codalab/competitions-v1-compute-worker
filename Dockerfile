FROM python:3

# Install a specific version of docker
RUN curl -sSL https://get.docker.com/ | sed 's/docker-ce/docker-ce=18.03.0~ce-0~debian/' | sh

# Install entr which is a file watching library
RUN apt-get install -y entr git

# Move into our worker directory, so we're not in /
WORKDIR /worker/

# Install Python stuff we need to listen to the queue
COPY requirements.txt /worker/requirements.txt
RUN pip install -r requirements.txt
RUN git clone https://github.com/igormusinov/cloud-hunky
RUN pip install -e ./cloud-hunky

# Copy our actual code
COPY *.py /worker/
COPY codalabworker /worker/codalabworker/
COPY codalabworker/detailed* /worker/
COPY logging.yaml /log/

# Run it
CMD celery worker -A $WORKER -l info -Q compute-worker -n compute-worker -Ofast -Ofair --concurrency=1
