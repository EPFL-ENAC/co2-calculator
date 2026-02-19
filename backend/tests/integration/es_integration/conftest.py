"""Configuration file for elasticsearch integration tests."""

import time

import docker
import pytest
from elasticsearch import Elasticsearch


@pytest.fixture(scope="session")
def docker_client():
    """Create a Docker client for managing containers."""
    return docker.from_env()


@pytest.fixture(scope="session")
def elasticsearch_container(docker_client):
    """Spin up an Elasticsearch container for integration tests."""
    # Define container configuration
    image = "docker.elastic.co/elasticsearch/elasticsearch:8.11.3"
    port = 9200
    container_name = "test-elasticsearch"

    # Environment variables for Elasticsearch
    env_vars = {
        "discovery.type": "single-node",
        "xpack.security.enabled": "false",
        "ES_JAVA_OPTS": "-Xms1g -Xmx1g",
    }

    try:
        # Remove any existing container with the same name
        try:
            old_container = docker_client.containers.get(container_name)
            old_container.remove(force=True)
        except docker.errors.NotFound:
            pass

        # Pull the image if not present
        try:
            docker_client.images.get(image)
        except docker.errors.ImageNotFound:
            print(f"Pulling Elasticsearch image: {image}")
            docker_client.images.pull(image)

        # Start the container
        container = docker_client.containers.run(
            image=image,
            name=container_name,
            ports={"9200/tcp": port},
            environment=env_vars,
            detach=True,
            remove=True,
        )

        # Wait for Elasticsearch to be ready
        timeout = 60  # seconds
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                container.reload()
                if container.status == "running":
                    # Check if Elasticsearch is responding
                    import requests

                    response = requests.get(f"http://localhost:{port}", timeout=1)
                    if response.status_code == 200:
                        print("Elasticsearch container is ready!")
                        break
            except Exception:
                pass
            time.sleep(1)
        else:
            raise Exception("Elasticsearch container failed to start within timeout")

        yield {"host": "localhost", "port": port, "container": container}

    finally:
        # Cleanup: Stop and remove the container
        try:
            container = docker_client.containers.get(container_name)
            container.stop(timeout=10)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            print(f"Error stopping container: {e}")


# Create the elasticsearch client fixture that connects to our Docker container
@pytest.fixture
def elasticsearch(elasticsearch_container):
    """Create an Elasticsearch client connected to the Docker container."""
    client = Elasticsearch(
        hosts=[
            f"http://{elasticsearch_container['host']}:{elasticsearch_container['port']}"
        ],
        verify_certs=False,
        request_timeout=30,
    )

    # Wait for the client to be ready
    timeout = 30
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            if client.ping():
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise Exception("Could not connect to Elasticsearch client within timeout")

    return client
