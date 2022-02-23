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
    version='0.2.10',
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
        'api': ['fastapi~=0.74.1', 'uvicorn~=0.17.5'],
        'storage': ['aiobotocore~=2.1.1'],
        'queues': ['aiobotocore~=2.1.1'],
        'database-psql': ['sqlalchemy[asyncio]~=1.4.31', 'asyncpg~=0.25.0'],
        'requester': ['httpx~=0.22.0'],
        'web3': ['web3~=5.28.0'],
    },
)
