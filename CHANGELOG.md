# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MAJOR] Updated `MessageQueueProcessor` to use a list of `NotificationClients` to send server messages
- [MAJOR] Updated `SlackClient`  to post `messageText` instead of text
- [MINOR] Added `NotificationClient.py` abstract class to help send data to multiple platforms
- [MINOR] Added `DiscordClient.py` to send data discord server
- [MINOR] Added `calculate_diff_days` and `calculate_diff_years` to `date_util`
- [MINOR] Added `datetime_to_utc` to `date_util`

### Changed
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
