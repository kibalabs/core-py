# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MINOR] Updated `init_logging`, `init_json_logging` and `init_basic_logging` to set the loggers of the third-party libraries core uses (`DEFAULT_EXTERNAL_LOGGER_NAMES`: httpx2, httpcore2, sqlalchemy, aiosqlite, asyncpg, botocore, aiobotocore, azure, apscheduler, web3) to `WARNING`; pass `extraLoggerNames` to quieten more loggers on top of these, or `loggerNames` to replace them (`loggerNames=[]` keeps the previous behaviour). `init_external_loggers` takes the same arguments and now defaults to the same list
- [MAJOR] Updated `Requester` to raise `RequesterTimeoutException` (a `GatewayTimeoutException`, 504) instead of `httpx` timeout exceptions; it carries the method, the URL without credentials or query string, the timeout, how long the request ran and the `httpx` timeout type, and keeps the original exception as its cause. Code catching `httpx.TimeoutException` (or `ReadTimeout`, `ConnectTimeout`, …) around `Requester` calls must catch `RequesterTimeoutException` instead
- [PATCH] Updated `MessageQueueProcessor` failure notifications to show the exception type before its message, so failures from exceptions without text (e.g. `httpx` timeouts) are still identifiable
- [MINOR] Added `authorize_bearer_jwt_request` for validating bearer JWTs in `RouteAuthResolver` implementations; it and `authorize_bearer_jwt` now only strip the leading `Bearer ` prefix, let cancellation propagate, and log why a JWT was rejected
- [MINOR] Made the `route` `authResolver` optional for routes without `auth`; setting `auth` without an `authResolver` raises `ValueError` at registration
- [MAJOR] Replaced `MessageQueue.delete_message` with `complete_message`, and added abstract `retry_message` (reschedule with a delay) and `fail_message` (apply the queue's failure policy); `MessageQueueProcessor` now reschedules `MessageNeedsReprocessingException` messages with `retry_message`
- [MINOR] Updated `MessageQueueProcessor` to retry messages that raise `LockedException` up to 3 times (30s linear backoff) before failing them
- [MINOR] Updated `MessageQueueProcessor` to log instead of raise when a failure notification cannot be sent
- [MAJOR] Reworked `SqlMessageQueue` to keep message history in `tbl_queue_messages` with a `status` lifecycle (`pending`, `running`, `succeeded`, `failed`, `deduplicated`), `owner`, `lastError`, `startedDate` and `completedDate`; deduplication now only applies against pending messages and keeps the earliest `visibleDate` of the duplicates, every retry, failure retry and lease-expiry reclaim increments `postCount`, failures back off and move to `failed` once `postCount` reaches `maxAttempts`, and `get_message_count` removes finished messages older than `retentionSeconds` (default 7 days) unless `shouldSkipRemovingNonRetained` is set
- [MINOR] Added `Database.now` to build database-clock timestamps; `SqlMessageQueue` and `SqlLock` now use the database clock instead of the host clock
- [MINOR] Capped `SqsMessageQueue` delays at SQS's 900 second maximum
- [MINOR] Updated `CosmosMessageQueue.retry_message` to reschedule the message in place and added emulator-backed tests (run when `CORE_TEST_COSMOS_ENDPOINT` is set)
- [MINOR] Added `shouldRaiseOnUncommittedWrites` to `Database` to raise instead of log when an isolated context connection is opened after uncommitted writes (for tests and development)
- [MAJOR] Added abstract `MessageQueue.extend_message_lease` (implemented for SQL, SQS, AQS and Cosmos queues, each returning `False` once the lease is lost; SQS accepts any receipt handle for a message so it can only detect that the message was deleted or is no longer in flight); `MessageQueueProcessor` now keeps a message's lease alive while it is being processed and, if the lease was lost, raises `MessageLeaseLostException` once the job returns (taking priority over any exception from the job, while cancellation still propagates) so the message is neither completed nor retried; `SqsMessageQueue` and `AqsMessageQueue` `retry_message` check the lease is still held before re-sending so a lost lease cannot duplicate the message
- [MINOR] Added optional `endpointUrl` to `SqsMessageQueue` and `AqsMessageQueue` to target local emulators, and added emulator-backed tests (run when `CORE_TEST_SQS_ENDPOINT` / `CORE_TEST_AQS_ENDPOINT` are set)
- [MINOR] Added `Lock.ensure_held` to renew a lease and raise `LockedException` if it has been lost, for use before irreversible work; `LockLease` now records its `ttlSeconds`
- [MINOR] Added `Lock` with a lease-based `SqlLock` implementation (`tbl_locks`) and a `with_lock` context manager that keeps the lease alive; acquiring raises `LockedException` (naming the current holder) if not acquired within `maxWaitSeconds`, and `get_owner` reports who holds a lock
- [MINOR] Added `process_util.get_process_name` to identify the current process (`<containerName>:<containerId>` in docker, `<hostname>:<pid>` otherwise)
- [MINOR] Added `Database.create_isolated_context_connection` to run a block in its own committed transaction inside an existing context connection; logs `ISOLATED_CONNECTION_AFTER_UNCOMMITTED_WRITES` when opened while the outer context connection has uncommitted writes
- [MAJOR] Added abstract `MessageQueue.get_message_count` (implemented for SQS, AQS, SQL and Cosmos queues) for the number of messages waiting to be processed
- [MAJOR] Added abstract `MessageQueue.get_inflight_message_count` (implemented for SQS, SQL and Cosmos queues; AQS raises `NotImplementedError` as Azure does not expose it) for the number of messages currently being processed
- [MAJOR] Reworked `route` to compose JSON or streaming transport, application-resolved authorization, and rate limiting
- [MAJOR] Replaced authorization-decorator sequences with named `RouteAuthResolver` policies
- [MINOR] Added `authJwt`, `authBasic`, and `originIp` to `KibaApiRequest`
- [MAJOR] Replaced global request-context accessors with injectable `RequestContextHolder` and `RequestContextMiddleware`
- [MINOR] Added `RateLimitConfig` for rate-limit windows and request keying
- [MINOR] Updated `json_route` and `streaming_json_route` to only parse and serialize requests and responses
- [MINOR] Added OpenAPI tag ordering, `OpenApiSecurityScheme` declarations, and route security metadata
- [MINOR] Added OpenAPI security-scheme publishing to authorization decorators
- [MINOR] Added `authorize_token_request` and `authorize_static_token_request` for token validation
- [MAJOR] Replace `httpx` with `httpx2` for HTTP requests
- [MINOR] Use `json_util`/`orjson` for API and database JSON serialization
- [MINOR] Use Pydantic `JsonValue` for JSON type aliases
- [MAJOR] Update web3 to 7.8.0
- [MINOR] Added `call_function_by_name`, `send_transaction_by_name` and `wait_for_transaction_receipt` to `RestEthClient`
- [MINOR] Updated `RestEthClient` to use `maxPriorityFeePerGas` and `maxFeePerGas` instead of `gasPrice`
- [MAJOR] Make all datetimes timezone aware
- [MINOR] Added `Cache`, `FileCache` and `DictCache`
- [MINOR] Added `url_util.encode_url`, `url_util.encode_url_part`, `url_util.decode_url` and `url_util.decode_url_part`
- [MINOR] Added `http_util.CACHABLE_STATUS_CODES`
- [PATCH] Moved `Requester` into a folder with same path as original
- [MINOR] Added `date_util.datetime_from_date`
- [MINOR] Add `json_util.dumps` and `json_util.loads` to use faster json serialization
- [MINOR] Update `DatabaseConnectionMiddleware` to not run for endpoints with `-streamed` suffix
- [MINOR] Added `shouldBackoffRetryOnRateLimit` and `retryLimit` to `RestEthClient` to deal with 429s
- [MINOR] Added `encode_transaction_data` to `chain_util` to support casting ints from hex-str when possible
- [MAJOR] Removed `RestEthClient._find_abi_by_name_args` - use chain_util function instaad
- [MINOR] Added `chain_util.encode_transaction_data_by_name`
- [MINOR] Added `list_util.remove_nones`
- [MAJOR] Added `maxWaitSeconds` with default=120 to `EthClient.wait_for_transaction_receipt`
- [MINOR] Added `async_util.gather_batched` function to `async_util`
- [MINOR] Added more exception classes
- [MAJOR] Added `apiPathPattern` to `logging.api`
- [MAJOR] Added `chainId` to `EthClientInterface`
- [MINOR] Added `call` and `multicall` to `EthClientInterface`
- [MINOR] Truncate discord notification messages to fit api
- [MINOR] Added `blockNumber` to `EthClient.multicall` function
- [MINOR] Added `SqlMessageQueue` and `CosmosMessageQueue` to support database backed queues
- [MINOR] Added `shouldAllowFailures` to `EthClient.multicall` to allow individual calls to fail without reverting the whole batch
- [MINOR] Added `KibaException.from_headers`/`outgoing_headers` hooks so exceptions can be built from and emit response headers; used by `TooManyRequestsException` (`Retry-After`, now also parsed automatically by `Requester` from 429 responses) and `RedirectException` (`Location`/`Cache-Control`), and applied generically by `ExceptionHandlingMiddleware`

### Changed

### Removed

## [0.5.2] - 2024-08-22

### Added
- [MAJOR] Updated `MessageQueueProcessor` to use a list of `NotificationClients` to send server messages
- [MAJOR] Updated `SlackClient`  to post `messageText` instead of text
- [MINOR] Added `NotificationClient.py` abstract class to help send data to multiple platforms
- [MINOR] Added `DiscordClient.py` to send data discord server
- [MINOR] Added `calculate_diff_days` and `calculate_diff_years` to `date_util`
- [MINOR] Added `datetime_to_utc` to `date_util`
- [MINOR] Added `init_external_loggers` to `logging`
- [MINOR] Added `end_of_day` to `date_util`
- [MINOR] Added `aiosqlite engine` to `database`
- [MINOR] Added core-api extra to server APIs with starlette only, no fastapi:
    - Added `core.http.jwt.Jwt`
    - Added `core.http.rest_method.RestMethod`
    - Added `core.api.api_request.KibaApiRequest`
    - Added `core.api.api_response.KibaJSONResponse`
    - Added `core.api.authorizer.authorize_bearer_jwt`
    - Added `core.api.json_route.json_route`

### Changed
- [MAJOR] Moved SlackClient to `core.notifications`
- [MAJOR] Moved DiscordClient to `core.notifications`
- [MAJOR] Moved NotificationClient to `core.notifications`
- [MINOR] Updated `Requester` to send data correctly for PUT requests
- [MINOR] Updated `Requester` to send data correctly for PATCH requests

### Removed

## [0.5.1] - 2023-02-16

### Added
- [MINOR] Added `call_contract_function` to `EthClientInterface`
- [MINOR] Added `_insert_record`, `_update_records`, and `_delete_records` to `Saver`
- [MINOR] Added `core.queues.aqs.AqsMessage` and `core.queues.aqs.AqsMessageQueue` to work with Azure Queues
- [MINOR] Added `BooleanFieldFilter` to `Retriever`

### Changed
- [MAJOR] Moved `SqsMessage` and `SqsMessageQueue` to `core.queues.sqs`

## [0.5.0] - 2022-11-08

### Added
- [MINOR] Added `requestId` to `Message`

### Changed
- [MINOR] Updated `Saver` to throw `SavingException` when saving fails
- [MINOR] Added `MessageNeedsReprocessingException` to `MessageQueueProcessor` to support rescheduling a message
- [MINOR] Use `www-authenticate` as message (if available) in 401 responses
- [MAJOR] Upgraded to sqlalchemy2

## [0.4.0] - 2022-07-19

### Added
- [MINOR] Added `head_file` to `S3Manager`
- [MAJOR] Added exception lists to `exceptions`
- [MINOR] Added `generate_clock_hour_intervals`, `generate_hourly_intervals`, `generate_datetime_intervals`, `generate_dates_in_range` to `date_util`

### Changed
- [MINOR] Updated `DatabaseConnectionMiddleware` to only create a transaction for non-GET requests
- [MAJOR] Updated `Requester` to throw specific exception types
- [MINOR] Updated `Requester.post_form` and `Requester.make_request` to accept `formFiles` parameter
- [MINOR] Added `shouldAddCacheHeader` to relevant `RedirectException`s

## [0.3.0] - 2022-04-23

### Added
- [MINOR] Added `send_messages` to `SqsMessageQueue` for sending multiple messages in one request
- [MINOR] Added `Database` to make facilitate easy migration from databases package
- [MINOR] Added `get_block_uncle_count` to `EthClient`
- [MINOR] Added `shouldFollowRedirects` to `Requester`
- [MINOR] Added `DatabaseConnectionMiddleware` to manage api database connections
- [MAJOR] Added `logging` module for custom kiba log formatting
- [MAJOR] Added `ExceptionHandlingMiddleware` to replace KibaRoute
- [MAJOR] Added `ServerHeadersMiddleware` to replace KibaRoute
- [MAJOR] Added `LoggingMiddleware` to replace KibaRoute
- [MAJOR] Added `requestIdHolder` to `MessageQueueProcessor`

### Changed
- [MAJOR] Replaced use of databases package in `Saver` and `Retriever`
- [MINOR] Update `Requester` to follow redirects by default
- [MAJOR] Replaced use of `boto3` with `aiobotocore` for S3Manager
- [MAJOR] Replaced use of `boto3` with `aiobotocore` for SqsMessageQueue

### Removed
- [MAJOR] Removed `KibaRouter` and `KibaRoute` - Use middlewares instead

## [0.2.10] - 2022-01-24

### Changed
- [MINOR] Updated `RestEthClient` to throw `BadRequestException` for malformed responses

## [0.2.9] - 2022-01-20

### Added
- [MINOR] Added `shouldHydrateTransactions` to `EthClient.get_block`

## [0.2.8] - 2022-01-17

### Added
- [MINOR] Added `postDate` to `Message`

### Changed
- [MINOR] Set `Message.postDate` in `SqsMessageQueue` when posting to queue

## [0.2.7] - 2022-01-15

### Added
- [MINOR] Added parallel processing to `MessageQueueProcessor.execute_batch`

## [0.2.6] - 2022-01-06

### Changed
- [PATCH] Fixed `MessageQueueProcessor` to allow limitless processing

## [0.2.5] - 2022-01-06

### Added
- [MINOR] Added batch processing to `MessageQueueProcessor`
- [MINOR] Added one-off processing to `MessageQueueProcessor`

## [0.2.4] - 2021-11-19

### Added
- [MINOR] Added `BURN_ADDRESS` to `chain_util`
- [MINOR] Added `RedirectException` and subclasses

### Changed
- [MINOR] Handle converting `RedirectException` to correct response in `KibaRoute`

## [0.2.3] - 2021-10-11

### Added
- [MINOR] Added `chain_util` with `normalize_address`

### Changed
- [MINOR] Updated to databases v0.5.1
- [MINOR] Updated `MessageQueueProcessor` to make `slackClient` optional

## [0.2.2] - 2021-08-21

### Changed
- [MINOR] Reverted `Message.COMMAND` change from 0.2.1
- [MINOR] Added `Message.get_command()` to prevent private access lint error

## [0.2.1] - 2021-08-18

### Changed
- [MINOR] Added `Message.COMMAND` and deprecation note on `Message._COMMAND` to suit linters

## [0.2.0] - 2021-08-08

### Added
- [MINOR] Added `post_form` to `Requester`
- [MINOR] Added `BasicAuthentication`

### Changed
- [MAJOR] Updated `Requester.post_json` to not accept data
- [MAJOR] Updated `file_util.create_directory` to be async

## [0.1.3] - 2021-07-14

### Added
- [MINOR] Added `create_directory` to `file_util`

### Changed
- [MINOR] Fix `Requester` to use dataDict correctly for GET params

## [0.1.2] - 2021-06-09

### Added
- [MINOR] Added `EthClient`

## [0.1.1] - 2021-05-20

### Added
- [MINOR] Added `IntegerFieldFilter` and `FloatFieldFilter` to `Saver`

## [0.1.0] - 2021-05-18

Initial Commit
