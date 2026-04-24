# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### 2026-04-24
- Improved documentation and README to align with the latest configuration schema
- Implemented lazy-loading protocol architecture for flexible display communication
- Added sound notification toggle to configuration
- Centralized hardware configuration and connection management in `DisplayBoard`
- Enhanced logging with numerical sorting, full athlete names, and consolidated board state representation
- Added support for deferred display updates (batching) and targeted area resets
- Implemented Microgate GRAPH protocol "Stop" command
- Refactored `config.json` structure for better organization (hardware block)

### 2026-04-23
- reset function called when exiting
- improved pagination
- improved config for board dimensions and font

### 2026-04-20
- update documentation and config

### 2026-04-19
- major refactor of config and code, remove alfa protocol

### 2026-04-18
- pain_special for multi physical boards
- advanced viz enabled
- working 2x2 and 1x1 table

### 2026-04-17
- make into package
- update pyproject
- correct pagination
- working pagination one column

### 2026-04-11
- add graphic protocol and improve pagination

### 2026-04-04
- update on installation
- make into an installable package
- add readme
- use display manager to alternate if close arrivals
