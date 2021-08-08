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
    version='0.2.0',
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
        'api': ['fastapi==0.52.0', 'uvicorn==0.13.4'],
        'storage': ['boto3==1.12.49'],
        'queues': ['boto3==1.12.49'],
        # NOTE(krishan711): 1.4.0 fail with wierd asyncpg error
        'database-psql': ['databases[postgresql]==0.4.2', 'sqlalchemy==1.3.23'],
        'requester': ['httpx==0.17.0'],
        'web3': ['web3==5.17.0'],
    },
)
