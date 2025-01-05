# Changelog

All notable changes to rosbackup-ng.

## [Unreleased]

### Added
- New CLI options for controlling parallel execution (`--no-parallel`, `--max-parallel`)
- Added ```--target``` option to run backup on specific target only
- Progress bar support with `-b` flag showing overall backup progress
- Improved logging with cleaner output and reduced duplication
- Support for keeping both binary and plaintext backups on routers

### Changed
- Enhanced target filtering and validation in CLI
- Improved SSH configuration structure in targets.yaml to match global.yaml
- Made SSH configuration more consistent between global and target settings
- Unified SSH argument handling for better inheritance and overrides
- Suppressed log messages when using progress bar mode
- Updated logging format for better readability
- Improved error handling in backup operations

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
  - `compress`: Enable transport layer compression
  - `auth_timeout`: Authentication response timeout
  - `channel_timeout`: Channel open timeout
  - `disabled_algorithms`: Dict of algorithms to disable
  - `keepalive_interval`: Seconds between keepalive packets
  - `keepalive_countmax`: Max keepalive failures before disconnect

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
