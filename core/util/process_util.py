import os
import re
import socket

DOCKERENV_PATH = '/.dockerenv'
MOUNTINFO_PATH = '/proc/self/mountinfo'
_DOCKER_CONTAINER_ID_PATTERN = re.compile(r'/containers/([0-9a-f]{64})/')


def is_running_in_docker() -> bool:
    return os.path.exists(DOCKERENV_PATH)


def get_docker_container_id() -> str:
    try:
        with open(MOUNTINFO_PATH, encoding='utf-8') as mountInfoFile:
            match = _DOCKER_CONTAINER_ID_PATTERN.search(mountInfoFile.read())
    except OSError:
        match = None
    # NOTE(krishan711): docker sets the hostname to the short container id unless --hostname is passed
    return match.group(1)[:12] if match else socket.gethostname()


def get_process_name(containerName: str | None = None) -> str:
    if is_running_in_docker():
        containerId = get_docker_container_id()
        return f'{containerName}:{containerId}' if containerName else containerId
    return f'{socket.gethostname()}:{os.getpid()}'
