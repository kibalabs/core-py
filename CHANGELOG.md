# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) with some additions:
- For all changes include one of [PATCH | MINOR | MAJOR] with the scope of the change being made.

## [Unreleased]

### Added
- [MINOR] Added `post_form` to `Requester`
- [MINOR] Added `BasicAuthentication`

### Changed
- [MAJOR] Updated `Requester.post_json` to not accept data
- [MAJOR] Updated `file_util.create_directory` to be async

### Removed

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
