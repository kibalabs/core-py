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
    version='0.5.0',
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
        'api': ['fastapi~=0.88.0', 'uvicorn[standard]~=0.20.0'],
        'storage': ['aiobotocore~=2.4.1'],
        'queues': ['aiobotocore~=2.4.1'],
        'database-psql': ['sqlalchemy[asyncio]~=2.0.0b3', 'asyncpg~=0.27.0'],
        'requester': ['httpx~=0.23.1'],
        'web3': ['web3==6.0.0-beta.8'],
        'types': [
            'types-aiobotocore[essential]~=2.4.1',
            'types-aiofiles~=22.1.0.4',
        ]
    },
)
