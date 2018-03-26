FROM python:2.7

# Install a specific version of docker
RUN curl -sSL https://get.docker.com/ | sed 's/docker-ce/docker-ce=18.03.0~ce-0~debian/' | sh

# Move into our worker directory, so we're not in /
WORKDIR /worker/

# Install Python stuff we need to listen to the queue
COPY requirements.txt /worker/requirements.txt
RUN pip install -r requirements.txt

# Copy our actual code
COPY *.py /worker/

# Run it
CMD celery -A worker worker -l info -Q compute-worker -n compute-worker -Ofast -Ofair --concurrency=1
