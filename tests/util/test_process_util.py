import os
import socket

import pytest

from core.util import process_util

CONTAINER_ID = 'a1b2c3d4e5f6' + '0' * 52


@pytest.fixture
def dockerPaths(tmp_path, monkeypatch):
    dockerEnvPath = tmp_path / '.dockerenv'
    mountInfoPath = tmp_path / 'mountinfo'
    monkeypatch.setattr(process_util, 'DOCKERENV_PATH', str(dockerEnvPath))
    monkeypatch.setattr(process_util, 'MOUNTINFO_PATH', str(mountInfoPath))
    return dockerEnvPath, mountInfoPath


def test_outside_docker_uses_hostname_and_pid(dockerPaths):
    assert process_util.get_process_name(containerName='yieldseeker-worker') == f'{socket.gethostname()}:{os.getpid()}'


def test_in_docker_uses_container_name_and_short_container_id(dockerPaths):
    dockerEnvPath, mountInfoPath = dockerPaths
    dockerEnvPath.touch()
    mountInfoPath.write_text(f'1 2 0:3 / /proc rw - proc proc rw\n4 5 259:1 /var/lib/docker/containers/{CONTAINER_ID}/hostname /etc/hostname rw - ext4 /dev/root rw\n')
    assert process_util.get_process_name(containerName='yieldseeker-worker') == 'yieldseeker-worker:a1b2c3d4e5f6'
    assert process_util.get_process_name() == 'a1b2c3d4e5f6'


def test_in_docker_falls_back_to_hostname_when_container_id_is_unreadable(dockerPaths):
    dockerEnvPath, _ = dockerPaths
    dockerEnvPath.touch()
    assert process_util.get_process_name(containerName='yieldseeker-worker') == f'yieldseeker-worker:{socket.gethostname()}'
