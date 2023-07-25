import os

from setuptools import find_packages
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
    version='0.5.1',
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
        'api': ['fastapi~=0.100.0', 'uvicorn[standard]~=0.23.1'],
        'storage': ['aiobotocore~=2.5.2'],
        # TODO(krishan711): remove this in next major update
        'queues': ['aiobotocore~=2.5.2'],
        'queue-sqs': ['aiobotocore~=2.5.2'],
        'queue-aqs': ['azure-storage-queue~=12.6.0'],
        'database-psql': ['sqlalchemy[asyncio]~=2.0.19', 'asyncpg~=0.28.0'],
        'requester': ['httpx~=0.24.1'],
        'web3': ['web3==6.6.1'],
        'types': [
            'types-aiobotocore[essential]~=2.5.2',
            'types-aiofiles~=23.1.0.5',
        ]
    },
)
