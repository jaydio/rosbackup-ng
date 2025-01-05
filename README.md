# RouterOS Backup NG (rosbackup-ng)

A robust Python-based utility for automating backups of multiple RouterOS devices via SSH. This tool supports both binary and plaintext backups, with features for backup retention management, parallel execution, and dry-run capabilities.

## Overview

### Core Features
- **Parallel Execution**: Back up 500 devices in under 1 minute! (since v0.1.0)
- **Flexible Backups**: Binary and plaintext (RouterScript) exports (since v0.1.0)
- **Comprehensive Logging**: Extensive logging with multiple levels and file rotation (since v0.1.0)
- **Email Notifications**: Built-in email notifications for backup status (since v0.1.0)
- **Dry-Run Mode**: Test configurations without making changes (since v0.1.0)
- **Progress Bar**: Visual progress tracking for parallel backups (since v0.1.5)
- **Automatic Router Setup**: Script for bootstrapping RouterOS devices with SSH keys and user permissions (since v0.1.4)
  - Supports force mode for overwriting existing users (since v0.1.6)

### Recent Enhancements
- **Enhanced Colors**: Distinct colors per router in logs with FORCE_COLOR/NO_COLOR support (v0.1.4)
- **Improved CLI**: Command-line auto-completion with target name support (v0.1.4)
- **SSH Config**: Better SSH configuration inheritance and flexibility (v0.1.4)
- **Target Control**: Run backups on specific targets with ```--target``` option (v0.1.4)
- **Parallel Control**: Fine-grained control over parallel execution (v0.1.4)
- **INFO Files**: Enhanced router information collection and formatting (v0.1.3)
- **Timezone Support**: Configurable timezone handling for timestamps (v0.1.3)
- **Progress Bar**: Added overall progress tracking with ETA for parallel backups (v0.1.5)

### Coming Soon
- **Notification Channels**: Support for Telegram, Slack/Mattermost, NTFY, and webhooks
- **Container Support**: Docker container and systemd timer support
- **Advanced Features**: Certificate store export/restore, batch processing
- **And more!** 

## Prerequisites

- Python 3.13.1 or higher
- RouterOS devices with SSH access enabled
- SSH key pair for authentication

## Command-Line Options

| Short | Long | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `-c` | `--config-dir` | "./config" | No | Directory containing configuration files |
| `-l` | `--log-file` | None | No | Override log file path. Only used if `log_file_enabled` is true |
| `-L` | `--log-level` | "INFO" | No | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `-d` | `--dry-run` | false | No | Simulate operations without making changes |
| `-n` | `--no-color` | false | No | Disable colored output |
| `-p` | `--no-parallel` | false | No | Disable parallel execution |
| `-m` | `--max-parallel` | None | No | Override maximum parallel backups (from global.yaml) |
| `-t` | `--target` | None | No | Run backup on specific target only |
| `-b` | `--progress-bar` | false | No | Show overall progress bar during parallel execution |
| `-f` | `--force` | false | No | Force mode for overwriting existing users |

## Examples

### Basic Usage
```bash
# Regular backup
./rosbackup.py

# Dry run to simulate backup operations
./rosbackup.py --dry-run

# Custom config directory
./rosbackup.py --config-dir /path/to/config

# Debug logging to file
./rosbackup.py --log-level DEBUG --log-file backup.log

# Disable colored output
./rosbackup.py --no-color

# Parallel execution control
./rosbackup.py --no-parallel              # Disable parallel execution
./rosbackup.py --max-parallel 10          # Set maximum parallel backups to 10

# Target selection
./rosbackup.py --target MYR1              # Backup specific target only

# Show progress bar during parallel backup
./rosbackup.py --progress-bar

# Progress bar with dry run
./rosbackup.py --progress-bar --dry-run

# Force mode for overwriting existing users
./rosbackup.py --force
```

## Directory Structure

```
.
├── backups/                    # Backup storage directory
├── config/                     # Configuration files
│   ├── global.yaml             # Global settings (user created)
│   ├── global.yaml.sample      # Global settings template
│   ├── targets.yaml            # Router definitions (user created)
│   └── targets.yaml.sample     # Router definitions template
├── core/                       # Core functionality modules
│   ├── backup_utils.py         # Backup operations and file handling
│   ├── logging_utils.py        # Logging system and formatters
│   ├── notification_utils.py   # Notification system (email, etc.)
│   ├── router_utils.py         # Router information gathering
│   ├── shell_utils.py          # Shell output formatting and colors
│   ├── ssh_utils.py            # SSH connections and operations
│   └── time_utils.py           # Timezone and timestamp operations
├── doc/                        # Documentation
│   ├── BOOTSTRAP.md            # Router setup guide
│   └── SETUP.md                # Installation and configuration
├── scripts/                    # Helper scripts
│   └── rosbackup-ng-completion.bash  # Shell completion
├── ssh-keys/                   # SSH key storage
│   ├── private/                # Private keys (user created)
│   └── public/                 # Public keys (user created)
├── bootstrap_router.py         # Router setup utility
├── rosbackup.py                # Main backup script
└── requirements.txt            # Python dependencies
```

## Backup File Organization

The backup files are organized in a structured hierarchy that reflects the router's identity and specifications:

```
backups/
└── {identity}_{host}_ROS{ros_version}_{arch}/    # Router-specific directory
    ├── {identity}_{ros_version}_{arch}_{timestamp}.backup    # Binary backup
    ├── {identity}_{ros_version}_{arch}_{timestamp}.rsc       # Plaintext export
    └── {identity}_{ros_version}_{arch}_{timestamp}.INFO.txt  # Router info
```

### Naming Convention

The backup files follow a standardized naming format that includes essential information about the router and backup:

- **Directory Name**: `{identity}_{host}_ROS{ros_version}_{arch}`
  - `identity`: Router's system identity (e.g., "HQ-ROUTER-01")
  - `host`: IP address or hostname (e.g., "192.168.1.1")
  - `ros_version`: RouterOS version (e.g., "7.10.2")
  - `arch`: Router architecture (e.g., "arm", "x86_64")

- **File Names**: `{identity}_{ros_version}_{arch}_{timestamp}.{ext}`
  - `identity`: Same as directory
  - `ros_version`: Same as directory
  - `arch`: Same as directory
  - `timestamp`: Backup creation time (format: DDMMYYYY-HHMMSS)
    - Uses system timezone by default
    - Can be overridden with `timezone` setting in global config
  - `ext`: File extension indicating type:
    - `.backup`: Binary backup file
    - `.rsc`: Plaintext configuration export
    - `.INFO.txt`: Router information and specifications

Example:
```
backups/
└── HQ-ROUTER-01_192.168.1.1_ROS7.10.2_arm/
    ├── HQ-ROUTER-01_7.10.2_arm_02012025-143022.backup
    ├── HQ-ROUTER-01_7.10.2_arm_02012025-143022.rsc
    └── HQ-ROUTER-01_7.10.2_arm_02012025-143022.INFO.txt
```

## Backup Types

### Binary Backup (.backup)
- Full system backup that can be used for complete system restore (same router model)
- Can be encrypted with a password (MikroTik proprietary)
- Contains all system settings, including:
  - Interface MAC addresses
  - Sensitive data
  - Certificate store
  - User database

### Plaintext Backup (.rsc)
- Human-readable script containing router configuration
- Uses RouterOS export command with following parameters:
  - `terse`: Produces single-line commands without wrapping
    - Makes output easier to process with tools like `grep`
    - Better for automated parsing and analysis
    - More consistent format across RouterOS versions
  - `show-sensitive`: Includes sensitive data like:
    - SNMP community strings
    - RADIUS secrets
    - PPP/PPTP/L2TP/SSTP/OVPN secrets
    - IPsec pre-shared keys
    - Wireguard private keys
- __<u>Does NOT include</u>__
  - Certificate store (will be added in a future version)
  - User database and user passwords (unsupported)
  - ZeroTier private key (unsupported)

## Configuration

The tool uses two YAML configuration files: `global.yaml` for general settings and `targets.yaml` for router-specific configurations.

### SSH Configuration

SSH settings can be configured both globally and per-target. The configuration follows a consistent structure in both files:

```yaml
# In global.yaml
ssh:
  user: rosbackup               # Default SSH username
  timeout: 5                    # Connection timeout in seconds
  auth_timeout: 5              # Authentication timeout in seconds
  known_hosts_file: null       # Optional: Path to known_hosts file
  add_target_host_key: true    # Whether to automatically add target host keys
  args:
    look_for_keys: false       # Whether to look for SSH keys in ~/.ssh/
    allow_agent: false         # Whether to use SSH agent
    compress: true             # Enable compression for slower connections
    auth_timeout: 5            # Authentication timeout in seconds
    channel_timeout: 5         # Channel timeout in seconds
    disabled_algorithms:       # Dict of algorithms to disable
      pubkeys: ["rsa-sha1"]   # Disable specific algorithms
    keepalive_interval: 60     # Send keepalive every minute
    keepalive_countmax: 3      # Disconnect after 3 failed keepalives

# In targets.yaml
targets:
  - name: HQ-ROUTER-01
    host: 192.168.88.1
    ssh:
      port: 22                 # SSH port number
      user: rosbackup          # Override global SSH username
      private_key: ./ssh-keys/private/id_rosbackup  # SSH private key path
      args:
        auth_timeout: 5        # Override global SSH arguments
        channel_timeout: 5
        compress: true
```

Target-specific SSH settings override global settings. The `args` section in both files accepts any valid Paramiko SSH client arguments.

### Configuration Inheritance

1. Global settings provide defaults for all targets
2. Target-specific settings override global settings
3. SSH arguments are merged, with target-specific args taking precedence
4. Common SSH arguments include:
   - `auth_timeout`: Authentication timeout in seconds
   - `channel_timeout`: Channel timeout in seconds
   - `compress`: Enable compression for slower connections
   - `keepalive_interval`: Interval between keepalive packets
   - `disabled_algorithms`: Dict of algorithms to disable

### Example Global Configuration

```yaml
# Backup Settings
backup_path_parent: backups
backup_retention_days: 90
backup_password: your-global-backup-password
timezone: Europe/Berlin  # Optional: Override system timezone for timestamps

# SSH Settings
ssh:
  user: rosbackup
  timeout: 30
  auth_timeout: 30
  known_hosts_file: null
  add_target_host_key: true
  args:
    look_for_keys: false
    allow_agent: false
    compress: true
    auth_timeout: 30
    channel_timeout: 30
    disabled_algorithms:
      pubkeys: ["rsa-sha1"]
    keepalive_interval: 60
    keepalive_countmax: 3

# Performance Settings
parallel_execution: true
max_parallel_backups: 5

# Logging Settings
log_file_enabled: true
log_file: ./rosbackup.log
log_level: INFO
log_retention_days: 90

# Notification Settings
notifications_enabled: true
notify_on_failed_backups: true
notify_on_successful_backups: false

# SMTP Settings
smtp:
  enabled: true
  host: smtp.example.com
  port: 587
  username: notifications@example.com
  password: your-smtp-password
  from_email: notifications@example.com
  to_emails: 
    - admin@example.com
  use_tls: true
  use_ssl: false
```

### Global Configuration Parameters

#### Backup Settings
| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `backup_path_parent` | string | "backups" | Yes | No | Parent directory for backups |
| `backup_retention_days` | integer | 90 | No | No | Days to keep backups |
| `backup_password` | string | null | No | Yes | Global backup password |
| `timezone` | string | uses system time | No | No | Timezone for timestamps (e.g. Asia/Manila) |

#### SSH Settings
| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `ssh.user` | string | rosbackup | Yes | Yes | SSH username for authentication |
| `ssh.timeout` | integer | 30 | No | Yes | Connection timeout in seconds |
| `ssh.auth_timeout` | integer | 30 | No | Yes | Authentication timeout in seconds |
| `ssh.known_hosts_file` | string | null | No | No | Path to SSH known_hosts file |
| `ssh.add_target_host_key` | boolean | true | No | No | Auto-add unknown host keys |
| `ssh.args.look_for_keys` | boolean | false | No | No | Search for discoverable private keys |
| `ssh.args.allow_agent` | boolean | false | No | No | Allow connecting to ssh-agent |
| `ssh.args.compress` | boolean | false | No | No | Enable transport layer compression |
| `ssh.args.auth_timeout` | integer | 30 | No | No | Authentication response timeout |
| `ssh.args.channel_timeout` | integer | 30 | No | No | Channel open timeout |
| `ssh.args.disabled_algorithms` | object | {} | No | No | Dict of algorithms to disable (see [here](https://docs.paramiko.org/en/stable/api/transport.html#paramiko.transport.Transport.disabled_algorithms) for details )|
| `ssh.args.keepalive_interval` | integer | 60 | No | No | Seconds between keepalive packets |
| `ssh.args.keepalive_countmax` | integer | 3 | No | No | Max keepalive failures before disconnect |

Example configuration with all SSH options:
```yaml
ssh:
  user: rosbackup
  timeout: 5  # Connection timeout
  auth_timeout: 5  # Authentication timeout
  known_hosts_file: null  # not saving known hosts to disk
  add_target_host_key: true
  args:
    look_for_keys: false
    allow_agent: false
    compress: true  # Enable for slower connections
    auth_timeout: 5
    channel_timeout: 5
    disabled_algorithms:  # Dict of algorithms to disable (see: https://docs.paramiko.org/en/stable/api/transport.html#paramiko.transport.Transport.disabled_algorithms)
      pubkeys: ["rsa-sha1"]  # Disable specific algorithms
    keepalive_interval: 60  # Send keepalive every minute
    keepalive_countmax: 3   # Disconnect after 3 failures
```

#### Performance Settings
| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `max_concurrent_backups` | integer | 5 | No | Maximum number of concurrent backups |
| `parallel_execution` | boolean | true | No | Enable parallel backup processing |

#### Logging Settings
| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `log_file` | string | "./rosbackup.log" | No | Path to the log file |
| `log_level` | string | "INFO" | No | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `log_file_enabled` | boolean | false | No | Enable logging to file in addition to console |
| `log_retention_days` | integer | 90 | No | Days to keep log files (-1 for infinite retention) |

#### Notification Settings
| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `notifications_enabled` | boolean | false | No | Master switch for all notifications |
| `notify_on_failed_backups` | boolean | true | No | Send notifications for failed backups |
| `notify_on_successful_backups` | boolean | false | No | Send notifications for successful backups |

#### SMTP Settings
| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `smtp.enabled` | boolean | false | No | Enable SMTP email notifications |
| `smtp.host` | string | - | Yes* | SMTP server hostname |
| `smtp.port` | integer | 587 | No | SMTP server port |
| `smtp.username` | string | - | Yes* | SMTP authentication username |
| `smtp.password` | string | - | Yes* | SMTP authentication password |
| `smtp.from_email` | string | - | Yes* | Sender email address |
| `smtp.to_emails` | array | - | Yes* | List of recipient email addresses |
| `smtp.use_tls` | boolean | true | No | Enable TLS encryption |
| `smtp.use_ssl` | boolean | false | No | Enable SSL encryption |

### Target Specific Configuration (targets.yaml)

Each router in the `targets` array supports the following parameters:

#### Example Configuration
```yaml
targets:
  - name: MYR1
    enabled: true
    host: 192.168.88.1
    ssh_port: 22
    ssh_user: rosbackup
    private_key: ./ssh-keys/private/id_rosbackup
    backup_password: SpecificPassword  # Override global backup password
    backup_retention_days: -1          # Keep backups indefinitely
    encrypted: true
    enable_binary_backup: true
    enable_plaintext_backup: true
    keep_binary_backup: false          # Remove after successful upload
    keep_plaintext_backup: false       # Remove after successful upload

  - name: MYR2
    enabled: true
    host: 192.168.88.2
    ssh_port: 22
    ssh_user: rosbackup
    private_key: ./ssh-keys/private/id_rosbackup
    encrypted: false                   # Do not encrypt backups
    enable_binary_backup: true
    enable_plaintext_backup: false     # Skip plaintext backups
```

#### Parameters
| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| `name` | string | - | Yes | Unique identifier for the router |
| `enabled` | boolean | true | No | Whether this router is enabled for backup |
| `host` | string | - | Yes | Router's hostname or IP address |
| `ssh_port` | integer | 22 | No | SSH port number |
| `ssh_user` | string | Global | No | SSH username |
| `private_key` | string | - | Yes | Path to SSH private key file |
| `encrypted` | boolean | false | No | Enable backup encryption |
| `enable_binary_backup` | boolean | true | No | Enable binary backup creation |
| `enable_plaintext_backup` | boolean | true | No | Enable plaintext backup creation |
| `keep_binary_backup` | boolean | false | No | Keep binary backup file on router |
| `keep_plaintext_backup` | boolean | false | No | Keep plaintext backup file on router |
| `backup_password` | string | Global | No | Override global backup password |
| `backup_retention_days` | integer | Global | No | Override global backup retention period |
| `ssh_args` | object | Global | No | Override global SSH arguments |

The following global parameters can be overridden on a per target basis:
- `backup_password`: Set a router-specific backup password
- `backup_retention_days`: Set a router-specific retention period
- `ssh_args`: Override any SSH connection parameters for this router

## Core Modules

This script is organized into core modules for better maintainability:

- **backup_utils.py**: Manages backup operations and file handling
- **logging_utils.py**: Configures logging system and formatters
- **notification_utils.py**: Handles notification system (email, etc.)
- **router_utils.py**: Handles gathering and formatting router information
- **shell_utils.py**: Manages shell output formatting and colors
- **ssh_utils.py**: Manages SSH connections and operations
- **time_utils.py**: Handles timezone and timestamp operations

## ROADMAP

The following features are planned for future releases.

### Notification Channels
- Telegram integration for backup status notifications
- NTFY.sh support for push notifications
- Mattermost/Slack webhook integration
- Generic webhook support for custom integrations
- [...]

Missing a feature? Open an issue or send a PR :)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
