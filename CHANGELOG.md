# Changelog

All notable changes to rosbackup-ng.

## [Unreleased]

### Added
- Improved logging format to include router name in log messages
- Added RouterLoggerAdapter for router-specific logging context

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
