# Changelog

## [0.4.0] - 2025-01-08

### Added
- Improved backup size tracking in compose-style output:
  * Added direct file tracking for accurate size calculations
  * Removed debug output from size calculation
  * Fixed incremental size updates during backup
- Enhanced compose-style output with better file handling and status updates
- Added proper handling of binary, plaintext, and info files in size calculations
- Added visual demo of compose-style output feature

### Changed
- Removed progress bar in favor of compose-style output
- Improved documentation with clearer examples and visual aids

## [Unreleased]

### Added
- Improved backup creation message to clearly indicate when a new backup file is created on the router

## [0.3.0] - 2025-01-07

### Added
- Added Docker Compose style output with improved state transitions and visual feedback
  * New ``--compose-style`` option for Docker Compose style output
- Added "Downloading" state to provide better visibility of backup progress
- Improved status handling to prevent state conflicts and ensure proper completion

### Fixed
- Fixed issue where the last router would hang in "Creating Backup" status
- Improved status update synchronization in parallel backup operations
- Enhanced screen updates to reduce flickering and provide smoother output

## [0.2.2] - 2025-01-07

### Fixed
- Fixed SSH key path resolution to be relative to project root instead of config directory
- Fixed tuple unpacking in SSH command execution results
- Improved error handling in dry-run mode
- Enhanced logging for SSH authentication and router access validation

## [0.2.1] - 2025-01-07

### Added
- Comprehensive type hints across all core modules:
  * Added return type hints for all methods
  * Added parameter type hints for all functions
  * Added proper typing for logging records
- Detailed docstrings with Args and Returns sections:
  * Added comprehensive function documentation
  * Improved error handling documentation
  * Added class-level documentation
- Message counter in log output for each target (e.g., [ROUTER #1])
- Random color assignment for targets with no duplicate colors
- Excluded white and green colors from target name coloring

### Changed
- Improved RouterInfo organization:
  * Split into logical sub-categories (SystemIdentityInfo, HardwareInfo, etc.)
  * Added detailed field descriptions
  * Better organization of network-related fields
- Enhanced logging formatters:
  * Improved BaseFormatter documentation and typing
  * Enhanced ColoredFormatter with better type safety
- Code cleanup:
  * Standardized docstring format
  * Improved type safety across modules
  * Better error handling documentation
- Improved log message format to use a cleaner, Kubernetes-inspired style

## [0.2.0] - 2025-01-06

### Added
- Parallel backup execution with configurable worker count
- Target-specific backup support with ``--target`` option
- Better type definitions in backup_utils.py:
  * Added `BackupConfig` TypedDict for global configuration
  * Added `TargetConfig` TypedDict with detailed field documentation
- Shell completion for both scripts:
  * Command-line option completion
  * File path completion
  * Target name completion from targets.yaml
- Comprehensive documentation:
  * Design reference with architecture and component flows
  * Command reference with detailed CLI options
  * Configuration reference with parameter details
  * Backup structure documentation
  * Filesystem structure documentation
  * Feature roadmap
  * Version information and format
- Demo GIF in README showing backup process
- Added .gitkeep to img directory for better repository structure

### Changed
- Improved error handling in backup operations:
  * Added exit status checks for RouterOS commands
  * Better error messages for failed operations
- Shell completion improvements:
  * Removed short-form parameters in favor of long-form only
- Documentation updates:
  * Expanded notification channels in roadmap
  * Added ramdisk backup feature to roadmap
  * Updated sample config with clearer comments
  * Updated README with cleaner output examples
  * Added visual demo section to README
  * Fixed typos in README
- Code cleanup:
  * Improved logging output format
  * Reduced duplicate log messages
  * Better error handling in SSH operations
- Improved documentation organization
- Updated README with visual demo section
- Fixed typos in README

## [0.1.6] - 2025-01-06

### Added
- Better type definitions in backup_utils.py:
  * Added `BackupConfig` TypedDict for global configuration
  * Added `TargetConfig` TypedDict with detailed field documentation
- Improved error handling in backup operations:
  * Added exit status checks for RouterOS commands
  * Better error messages for failed operations

### Changed
- Shell completion improvements:
  * Removed short-form parameters in favor of long-form only
- Documentation updates:
  * Expanded notification channels in roadmap
  * Added ramdisk backup feature to roadmap
  * Updated sample config with clearer comments
  * Updated README with cleaner dry-run output
- Code cleanup:
  * Improved logging output format
  * Reduced duplicate log messages
  * Better error handling in SSH operations

## [0.1.5] - 2025-01-06

### Added
- New CLI options for controlling parallel execution (`--no-parallel`, `--max-parallel`)
- Added ``--target`` option to run backup on specific target only
- Improved logging with cleaner output and reduced duplication
- Shell completion improvements:
  * Removed short-form parameters in favor of long-form only
- Comprehensive documentation:
  * Design reference with architecture and component flows
  * Command reference with detailed CLI options
  * Configuration reference with parameter details
  * Backup structure documentation
  * Filesystem structure documentation
  * Feature roadmap

### Changed
- Enhanced target filtering and validation in CLI
- Improved SSH configuration structure in targets.yaml to match global.yaml
- Made SSH configuration more consistent between global and target settings
- Unified SSH argument handling for better inheritance and overrides
- Updated logging format for better readability
- Improved error handling in backup operations
- Enhanced configuration documentation with clearer parameter descriptions

### Fixed
- SSH configuration inheritance when using target-specific settings
- Proper merging of SSH arguments from global and target configs

## [0.1.4] - 2025-01-05

### Added
- Enhanced colored output with distinct colors for each router
- Improved log readability with consistent color scheme
- Added support for FORCE_COLOR and NO_COLOR environment variables
- Improved logging format to include router name in log messages
- Added RouterLoggerAdapter for router-specific logging context

### Changed
- Refactored color handling in shell_utils.py
- Improved SSH configuration inheritance from global settings
- Updated log formatting for better visibility during parallel execution

## [0.1.3] - 2025-01-05

### Added
- Enhanced INFO file format with detailed sections:
  - Overall Statistics (IP addressing, interfaces, firewall rules, DHCP services, QoS and ARP/ND)
  - Time Settings (time, date, timezone, DST status)
- Added terse parameter to export command for cleaner output
- Improved logging with router/target names for better clarity

### Changed
- Changed timestamp format from DDMMYYYY to MMDDYYYY for consistency
- Updated backup naming convention and INFO file format
- Simplified timezone logging
- Improved timezone handling across the application

### Fixed
- Improved architecture detection and handling
- Enhanced router info parsing with better error handling
- Fixed duplicate logging messages
- Added more debug logging for routerboard info parsing
- Better support for CHR

### Documentation
- Added references to Paramiko disabled_algorithms documentation
- Improved SSH troubleshooting guide
- Removed outdated demo GIF (to be replaced)

### Not working
- Color output in rosbackup.py is currently non-functional

## [0.1.2] - 2025-01-03

### Added
- Added support for additional SSH parameters:
  - ``compress``: Enable transport layer compression
  - ``auth_timeout``: Authentication response timeout
  - ``channel_timeout``: Channel open timeout
  - ``disabled_algorithms``: Dict of algorithms to disable
  - ``keepalive_interval``: Seconds between keepalive packets
  - ``keepalive_countmax``: Max keepalive failures before disconnect

### Fixed
- Fixed SSH configuration key from 'ssh_args' to 'ssh' to match documentation
- Updated SSH timeout defaults to 5 seconds for faster failure detection

## [0.1.1] - 2025-01-03

### Improved
- Enhanced type hints with TypedDict definitions across all core modules
- Improved documentation with error handling details and security notes
- Better help output for CLI scripts with practical examples
- Clearer setup and configuration instructions

## [0.1.0] - 2025-01-03

### Added
- Initial release of rosbackup-ng
- Binary and plaintext backup support
- Parallel execution for multiple devices
- SSH key-based authentication
- Encrypted backups
- Email notifications
- Backup retention management
- Bootstrap script for router setup
