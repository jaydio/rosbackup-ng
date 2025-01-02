# RouterOS Backup Script (rosbackup-ng)

A robust Python-based utility for automating backups of multiple RouterOS devices via SSH. This tool supports both binary and plaintext backups, with features for backup retention management, parallel execution, and dry-run capabilities.

## Features

- **Multiple Backup Types**: Supports both binary (.backup) and plaintext (.rsc) backups
- **Dry-Run Mode**: Safely simulate backup operations without making changes
- **Parallel Processing**: Efficiently backs up multiple devices simultaneously
- **Command-Line Completion**: Bash completion support for all options
- **Modular Architecture**: Well-organized core modules for better maintainability
- **Secure**: Uses SSH key-based authentication
- **Informative**: Generates detailed info files containing router specifications
- **Notification Support**: Integrated notification system for backup status updates
- **Consistent Naming**: All backup files follow a standardized naming format
- **Flexible Configuration**: Supports YAML configuration format

## Directory Structure

The project follows a modular structure for better organization and maintainability:

```
.
├── backups/                        # Backup storage directory
├── bootstrap_router.py             # Router setup utility
├── config/                         # Configuration files
│   ├── global.yaml                 # Global settings (user created)
│   ├── global.yaml.sample          # Global settings
│   ├── targets.yaml                # Router definitions (user created)
│   ├── targets.yaml.sample         # Router definitions
├── core/                           # Core functionality modules
│   ├── __init__.py                 # Package initialization
│   ├── backup_operations.py        # Backup operations management
│   ├── notifications.py            # Notification system
│   ├── router_info.py              # Router information gathering
│   └── ssh_utils.py                # SSH connection management
├── doc/                            # Documentation
│   ├── BOOTSTRAP.md                # Setup instructions
│   └── SETUP.md                    # Detailed configuration guide
├── scripts/                        # Helper scripts
│   └── rosbackup-completion.bash   # Command-line completion
├── ssh-keys/                       # SSH key storage
│   ├── private/                    # Private key directory
│   └── public/                     # Public key directory
├── LICENSE                         # MIT License
├── README.md                       # This file
├── requirements.txt                # Python dependencies
└── rosbackup.py                    # Main script
```

## Backup File Organization

The backup files are organized in a structured hierarchy that reflects the router's identity and specifications:

```
backups/
└── {identity}-{host}-ROS{ros_version}-{arch}/    # Router-specific directory
    ├── {identity}-{ros_version}-{arch}-{timestamp}.backup    # Binary backup
    ├── {identity}-{ros_version}-{arch}-{timestamp}.rsc       # Plaintext export
    └── {identity}-{ros_version}-{arch}-{timestamp}.INFO.txt  # Router info
```

### Naming Convention

The backup files follow a standardized naming format that includes essential information about the router and backup:

- **Directory Name**: `{identity}-{host}-ROS{ros_version}-{arch}`
  - `identity`: Router's system identity (e.g., "HQ-ROUTER-01")
  - `host`: IP address or hostname (e.g., "192.168.1.1")
  - `ros_version`: RouterOS version (e.g., "7.10.2")
  - `arch`: Router architecture (e.g., "arm", "x86_64")

- **File Names**: `{identity}-{ros_version}-{arch}-{timestamp}.{ext}`
  - `identity`: Same as directory
  - `ros_version`: Same as directory
  - `arch`: Same as directory
  - `timestamp`: Backup creation time (format: DDMMYYYY-HHMMSS)
  - `ext`: File extension indicating type:
    - `.backup`: Binary backup file
    - `.rsc`: Plaintext configuration export
    - `.INFO.txt`: Router information and specifications

Example:
```
backups/
└── HQ-ROUTER-01-192.168.1.1-ROS7.10.2-arm/
    ├── HQ-ROUTER-01-7.10.2-arm-02012025-143022.backup
    ├── HQ-ROUTER-01-7.10.2-arm-02012025-143022.rsc
    └── HQ-ROUTER-01-7.10.2-arm-02012025-143022.INFO.txt
```

## Details setup instructions

For detailed setup instructions and configuration guide, see:
- [Setup Guide](doc/SETUP.md): Comprehensive configuration and usage documentation
- [Bootstrap Tool](doc/BOOTSTRAP.md): Guide for initial router setup and configuration

## Quick Start

1. Ensure Python 3.6 or higher is installed

2. Set up Python virtual environment (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Create configuration files from samples
   ```bash
   cp config/global.yaml.sample config/global.yaml
   cp config/targets.yaml.sample config/targets.yaml
   ```

5. Set up SSH keys (choose one):
   ```bash
   # Option 1: Link existing keys
   ln -s ~/.ssh/id_rsa ssh-keys/private/id_rosbackup
   ln -s ~/.ssh/id_rsa.pub ssh-keys/public/id_rosbackup.pub
   
   # Option 2: Generate new keys
   ssh-keygen -t rsa -b 4096 -f ssh-keys/private/id_rosbackup -C "rosbackup"
   ```

6. Enable command-line completion (optional):
   ```bash
   source scripts/rosbackup-completion.bash
   ```

7. Configure RouterOS devices (choose one):
   ```bash
   # Option 1: Use bootstrap tool (recommended)
   python bootstrap_router.py --ip <router_ip> --backup-user-public-key <path_to_public_key>
   
   # Option 2: Manually configure SSH keys and permissions
   # See BOOTSTRAP.md for manual setup instructions
   ```

8. Run the backup script:
   ```bash
   ./rosbackup.py
   ```

## Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--config-dir` | "config" | Directory containing configuration files |
| `--log-file` | None | Log file path (optional) |
| `--log-level` | "INFO" | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `--dry-run` | false | Simulate operations without making changes |
| `--no-color` | false | Disable colored output |

## Configuration

### Global Settings

The global configuration file contains settings that apply to all backup operations:

Example (`global.yaml`):
```yaml
# Backup Settings
backup_path_parent: backups
backup_retention_days: 90
backup_password: your-global-backup-password

# SSH Settings
ssh_user: rosbackup
ssh_args:
  look_for_keys: false
  allow_agent: false

# Performance Settings
parallel_execution: true
max_parallel_backups: 5
```

### Router Definitions

The targets configuration file contains the list of routers to back up:

Example (`targets.yaml`):
```yaml
routers:
  - name: HQ-ROUTER-01
    enabled: true
    host: 192.168.1.1
    ssh_port: 22
    ssh_user: backup
    private_key: ./ssh-keys/private/id_rosbackup
    encrypted: true
    enable_binary_backup: true
    enable_plaintext_backup: true
```

### Configuration Parameters

#### Backup Settings
| Parameter | Type | Default | Overridable | Description |
|-----------|------|---------|-------------|-------------|
| `backup_path` | string | "backups" | No | Base directory for storing all router backups |
| `backup_retention_days` | integer | 90 | Yes | Days to keep backups (-1 for infinite retention) |
| `backup_password` | string | - | Yes | Default password for encrypted backups |

#### Performance Settings
| Parameter | Type | Default | Overridable | Description |
|-----------|------|---------|-------------|-------------|
| `max_concurrent_backups` | integer | 5 | No | Maximum number of concurrent backups |
| `parallel_execution` | boolean | true | No | Enable parallel backup processing |

#### Logging Settings
| Parameter | Type | Default | Overridable | Description |
|-----------|------|---------|-------------|-------------|
| `log_file` | string | "./rosbackup.log" | No | Path to the log file |
| `log_level` | string | "INFO" | No | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `enable_file_logging` | boolean | false | No | Enable logging to file in addition to console |
| `log_retention_days` | integer | 90 | No | Days to keep log files (-1 for infinite retention) |

#### SSH Settings
| Parameter | Type | Default | Overridable | Description |
|-----------|------|---------|-------------|-------------|
| `ssh_user` | string | "rosbackup" | Yes | Default SSH username |
| `ssh_args` | object | {} | Yes | SSH connection arguments |

The `ssh_args` object supports the following parameters (all overridable per target):

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `look_for_keys` | boolean | false | Search for discoverable private key files in ~/.ssh/ |
| `allow_agent` | boolean | false | Allow connecting to ssh-agent |
| `timeout` | integer | 10 | Connection timeout in seconds |
| `banner_timeout` | integer | 10 | Banner timeout in seconds |
| `auth_timeout` | integer | 10 | Authentication timeout in seconds |

#### Notification Settings
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notifications_enabled` | boolean | false | Master switch for all notifications |
| `notify_on_failed_backups` | boolean | true | Send notifications for failed backups |
| `notify_on_successful_backups` | boolean | false | Send notifications for successful backups |

#### SMTP Settings
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `smtp.enabled` | boolean | false | Enable SMTP email notifications |
| `smtp.host` | string | - | SMTP server hostname |
| `smtp.port` | integer | 587 | SMTP server port |
| `smtp.username` | string | - | SMTP authentication username |
| `smtp.password` | string | - | SMTP authentication password |
| `smtp.from_email` | string | - | Sender email address |
| `smtp.to_emails` | array | - | List of recipient email addresses |
| `smtp.use_tls` | boolean | true | Enable TLS encryption |
| `smtp.use_ssl` | boolean | false | Enable SSL encryption |

### Router Configuration (targets.yaml)

Each router in the `routers` array supports the following parameters:

| Parameter | Type | Default | Source | Description |
|-----------|------|---------|---------|-------------|
| `name` | string | Required | - | Unique identifier for the router |
| `host` | string | Required | - | Router's hostname or IP address |
| `ssh_port` | integer | 22 | - | SSH port number |
| `ssh_user` | string | Required | - | SSH username |
| `private_key` | string | Required | - | Path to SSH private key file |
| `encrypted` | boolean | true | - | Enable backup encryption |
| `enable_binary_backup` | boolean | true | - | Enable binary backup creation |
| `enable_plaintext_backup` | boolean | true | - | Enable plaintext backup creation |
| `keep_binary_backup` | boolean | false | - | Keep binary backup file on router |
| `keep_plaintext_backup` | boolean | false | - | Keep plaintext backup file on router |
| `backup_password` | string | - | global.yaml | Override global backup password |
| `backup_retention_days` | integer | - | global.yaml | Override global backup retention period |
| `ssh_args` | object | - | global.yaml | Override global SSH arguments |

The following parameters can be overridden from global.yaml:
- `backup_password`: Set a router-specific backup password
- `backup_retention_days`: Set a router-specific retention period
- `ssh_args`: Override any SSH connection parameters for this router

## Core Modules

The application is now organized into core modules for better maintainability:

- **backup_operations.py**: Manages backup operations
- **notifications.py**: Handles notification system
- **router_info.py**: Handles gathering and formatting router information
- **ssh_utils.py**: Manages SSH connections and operations

## Examples

### Basic Usage
```bash
# Regular backup
python rosbackup.py

# Dry-run mode
python rosbackup.py --dry-run

# Custom config directory
python rosbackup.py --config-dir /path/to/config

# Debug logging
python rosbackup.py --log-level DEBUG --log-file backup.log

# Disable colored output
python rosbackup.py --no-color
```

## ROADMAP

The following features are planned for future releases:

### Notification Channels
- Telegram integration for backup status notifications
- NTFY.sh support for push notifications
- Mattermost/Slack webhook integration
- Generic webhook support for custom integrations
- [...]

### Enhanced Backup & Restore
- Certificate store export functionality
- Remote restore capability including certificate store

### Automation & Scaling
- Batch processing support for `bootstrap_router.py`
- Enhanced parallel processing capabilities

## License

This project is licensed under the MIT License - see the LICENSE file for details.