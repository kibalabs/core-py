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
        'api': ['fastapi>=0.115.8', 'uvicorn[standard]>0.34.0'],
        'core-api': ['starlette>=0.45.3', 'uvicorn[standard]>0.34.0'],
        'storage': ['aiobotocore>=2.19.0'],
        # TODO(krishan711): remove this in next major update
        'queues': ['aiobotocore>=2.19.0'],
        'queue-sqs': ['aiobotocore>=2.19.0'],
        'queue-aqs': ['azure-storage-queue[aio]>=12.12.0'],
        'database-psql': ['sqlalchemy[asyncio]>=2.0.38', 'asyncpg>=0.30.0'],
        'database-sqlite': ['sqlalchemy[asyncio]>=2.0.38', 'aiosqlite>=0.21.0'],
        'requester': ['httpx>=0.28.1'],
        'web3': ['web3>=7.8.0'],
        'types': [
            'types-aiobotocore[essential]>=2.19.0',
            'types-aiofiles>=24.1.0.20241221',
        ]
    },
)
