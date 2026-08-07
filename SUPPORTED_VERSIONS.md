# Supported Versions

The SDK follows [Semantic Versioning](https://semver.org/). Security fixes are
applied to the latest minor release of the current major line.

| Version | Supported          |
|---------|--------------------|
| 3.1.x   | :white_check_mark: |
| 3.0.x   | :white_check_mark: |
| < 3.0   | :x:                |

## Supported Python versions

`aiqa` requires **Python 3.11+** and is tested on:

| Python | Supported          |
|--------|--------------------|
| 3.13   | :white_check_mark: |
| 3.12   | :white_check_mark: |
| 3.11   | :white_check_mark: |
| ≤ 3.10 | :x:                |

## Supported platforms

Windows, macOS, and Linux. The core SDK is pure Python and dependency-free;
optional features (e.g. an LLM provider) pull in extras only when enabled.
