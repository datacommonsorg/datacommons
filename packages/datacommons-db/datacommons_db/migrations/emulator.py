# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Spanner emulator discovery, container lifecycle, and ephemeral database management."""

import contextlib
import os
import shutil
import socket
import subprocess
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

from google.auth.credentials import AnonymousCredentials
from google.cloud import spanner
from google.cloud.spanner_v1.database import Database
from google.cloud.spanner_v1.instance import Instance

from datacommons_db.clients import SpannerClient

DEFAULT_EMULATOR_HOST = "localhost:9010"
DEFAULT_INSTANCE_ID = "default"


def is_emulator_reachable(host: str | None = None) -> bool:
    """Checks whether a Spanner emulator host is responding on its TCP port.

    Args:
        host: Host string (e.g. 'localhost:9010'). If omitted, defaults to
            $SPANNER_EMULATOR_HOST or 'localhost:9010'.

    Returns:
        True if the socket connects successfully within 1 second, False otherwise.
    """
    target = host or os.getenv("SPANNER_EMULATOR_HOST") or DEFAULT_EMULATOR_HOST
    try:
        parts = target.split(":")
        ip = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 9010
        sock = socket.create_connection((ip, port), timeout=1)
        sock.close()
        return True
    except (OSError, ValueError):
        return False


def get_docker_compose_path() -> Path:
    """Finds the local integration test docker-compose.yml file.

    Returns:
        Path to tests/integration/emulated/docker-compose.yml.
    """
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "tests" / "integration" / "emulated" / "docker-compose.yml"


def ensure_emulator_running(
    timeout_seconds: int = 20,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    """Discovers a reachable Spanner emulator or starts the local Docker container.

    Checks:
    1. SPANNER_EMULATOR_HOST environment variable.
    2. Default host 'localhost:9010'.
    3. Verifies Docker CLI on PATH and Docker daemon liveness.
    4. Auto-starts 'tests/integration/emulated/docker-compose.yml' via docker compose.

    Returns:
        The reachable emulator host string (e.g. 'localhost:9010').

    Raises:
        ConnectionError: If no emulator is reachable and auto-launch fails.
    """
    if progress_callback:
        progress_callback("🔍 Checking for Spanner emulator...")

    env_host = os.getenv("SPANNER_EMULATOR_HOST")
    if env_host and is_emulator_reachable(env_host):
        if progress_callback:
            progress_callback(f"✔ Using active Spanner emulator at '{env_host}'")
        return env_host

    if is_emulator_reachable(DEFAULT_EMULATOR_HOST):
        if progress_callback:
            progress_callback(
                f"✔ Found running Spanner emulator at {DEFAULT_EMULATOR_HOST}"
            )
        return DEFAULT_EMULATOR_HOST

    # Step 1: Check if Docker is installed on PATH
    if not shutil.which("docker"):
        raise ConnectionError(
            f"Spanner emulator is not reachable at '{DEFAULT_EMULATOR_HOST}' and Docker was not found on PATH.\n"
            "To generate the engine-collapsed schema, please install Docker Desktop and start the emulator:\n"
            f"    docker compose -f {get_docker_compose_path()} up -d spanner"
        )

    # Step 2: Check if Docker daemon is running
    try:
        daemon_check = subprocess.run(
            ["docker", "info"],  # noqa: S603, S607
            capture_output=True,
            timeout=5,
            check=False,
        )
        if daemon_check.returncode != 0:
            raise ConnectionError(
                f"Spanner emulator is not reachable at '{DEFAULT_EMULATOR_HOST}', and the Docker daemon is not running.\n"
                "Please start Docker Desktop and re-run the command."
            )
    except (subprocess.TimeoutExpired, OSError) as e:
        raise ConnectionError(
            "Failed to communicate with Docker daemon.\n"
            "Please ensure Docker Desktop is open and running."
        ) from e

    # Step 3: Attempt to automatically start the spanner emulator via docker compose
    compose_path = get_docker_compose_path()
    if compose_path.exists():
        if progress_callback:
            progress_callback(
                "🚀 Spanner emulator not running. Auto-starting container via docker compose..."
            )
        try:
            subprocess.run(  # noqa: S603
                ["docker", "compose", "-f", str(compose_path), "up", "-d", "spanner"],  # noqa: S607
                check=True,
                capture_output=True,
                timeout=45,
            )
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                if is_emulator_reachable(DEFAULT_EMULATOR_HOST):
                    if progress_callback:
                        progress_callback(
                            f"✔ Spanner emulator container started and ready at {DEFAULT_EMULATOR_HOST}"
                        )
                    return DEFAULT_EMULATOR_HOST
                time.sleep(0.5)
        except Exception as e:
            raise ConnectionError(
                f"Spanner emulator auto-launch failed: {e}.\n"
                f"Please start it manually via: docker compose -f {compose_path} up -d spanner"
            ) from e

    raise ConnectionError(
        "Spanner emulator did not become ready within the timeout period.\n"
        "Check container status with: docker ps\n"
        "Or check logs with: docker logs itest-spanner"
    )


def _get_or_create_instance(
    client: spanner.Client,
    instance_id: str = DEFAULT_INSTANCE_ID,
) -> Instance:
    """Discovers instance configuration and ensures the emulator instance exists."""
    configs = list(client.list_instance_configs())
    config_names = [c.name for c in configs]
    config_name = next(
        (c for c in config_names if "default" in c),
        next(
            (c for c in config_names if "emulator-config" in c),
            config_names[0]
            if config_names
            else f"{client.project_name}/instanceConfigs/default",
        ),
    )
    instance = client.instance(
        instance_id,
        configuration_name=config_name,
        display_name="Local Omni Instance",
        node_count=1,
    )
    if not instance.exists():
        instance.create().result(timeout=15)
    return instance


@contextlib.contextmanager
def ephemeral_emulator_database(
    project_id: str = "default",
    region: str = "us-central1",
    emulator_host: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> Iterator[tuple[spanner.Client, Database, SpannerClient]]:
    """Context manager provisioning an ephemeral database on the Spanner emulator.

    Guarantees that the ephemeral database is created, provided for execution,
    and reliably dropped upon exiting the context.

    Yields:
        Tuple of (google.cloud.spanner.Client, spanner Database, datacommons SpannerClient)
    """
    host = emulator_host or ensure_emulator_running(progress_callback=progress_callback)
    old_host = os.environ.get("SPANNER_EMULATOR_HOST")
    os.environ["SPANNER_EMULATOR_HOST"] = host

    client = spanner.Client(project=project_id, credentials=AnonymousCredentials())
    instance = _get_or_create_instance(client, DEFAULT_INSTANCE_ID)

    db_id = f"snap-{uuid.uuid4().hex[:8]}"
    if progress_callback:
        progress_callback(f"📦 Provisioning ephemeral in-memory database '{db_id}'...")

    db = instance.database(db_id)
    db.create().result(timeout=15)

    spanner_client = SpannerClient(
        project_id=project_id,
        instance_id=DEFAULT_INSTANCE_ID,
        database_id=db_id,
        credentials=AnonymousCredentials(),
        region=region,
    )

    try:
        yield client, db, spanner_client
    finally:
        if progress_callback:
            progress_callback("🧹 Cleaning up ephemeral database...")
        with contextlib.suppress(Exception):
            db.drop()
        if old_host is None:
            os.environ.pop("SPANNER_EMULATOR_HOST", None)
        else:
            os.environ["SPANNER_EMULATOR_HOST"] = old_host
