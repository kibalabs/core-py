import os

# NOTE: test-check reports skipped tests as failures, so cosmos tests are only collected when an emulator is configured
collect_ignore = [] if os.environ.get('CORE_TEST_COSMOS_ENDPOINT') else ['test_cosmos_queue.py']
