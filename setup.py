import os

from setuptools import find_packages  # type: ignore[import-untyped]
from setuptools import setup

setupDirectory = os.path.dirname(os.path.realpath(__file__))

requirements = []
with open(os.path.join(setupDirectory, 'requirements.txt'), 'r') as requirementsFile:
    for requirement in requirementsFile.read().splitlines():
        if requirement:
            requirements.append(requirement)

devRequirements = []
with open(os.path.join(setupDirectory, 'requirements-dev.txt'), 'r') as requirementsFile:
    for requirement in requirementsFile.read().splitlines():
        if requirement:
            devRequirements.append(requirement)

setup(
    name='kiba-core',
    version='0.5.2',
    description='Kiba Labs\' python utilities',
    url='https://github.com/kibalabs/core-py',
    packages=find_packages(exclude=['tests*']),
    python_requires='~=3.7',
    install_requires=requirements,
    tests_require=[],
    package_data={
        'core': [
            'py.typed',
        ]
    },
    test_suite='tests',
    include_package_data=True,
    extras_require={
        'api': ['fastapi~=0.112.1', 'uvicorn[standard]~=0.30.6'],
        'storage': ['aiobotocore~=2.13.2'],
        # TODO(krishan711): remove this in next major update
        'queues': ['aiobotocore~=2.13.2'],
        'queue-sqs': ['aiobotocore~=2.13.2'],
        'queue-aqs': ['azure-storage-queue~=12.11.0'],
        'database-psql': ['sqlalchemy[asyncio]~=2.0.32', 'asyncpg~=0.29.0'],
        'database-sqlite': ['sqlalchemy[asyncio]~=2.0.32', 'aiosqlite~=0.20.0'],
        'requester': ['httpx~=0.27.0'],
        'web3': ['web3==6.10.0'],
        'types': [
            'types-aiobotocore[essential]~=2.13.2',
            'types-aiofiles~=24.1.0.20240626',
        ]
    },
)
