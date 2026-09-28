import os

# NOTE: test-check reports skipped tests as failures, so emulator-backed tests are only collected when their emulator is configured
collect_ignore = [
    fileName
    for fileName, environmentVariable in {
        'test_cosmos_queue.py': 'CORE_TEST_COSMOS_ENDPOINT',
        'test_sqs_queue.py': 'CORE_TEST_SQS_ENDPOINT',
        'test_aqs_queue.py': 'CORE_TEST_AQS_ENDPOINT',
    }.items()
    if not os.environ.get(environmentVariable)
]
