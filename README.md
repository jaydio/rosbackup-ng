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

## Directory Structure

```
.
├── backups/                        # Backup storage directory
│   └── {identity}-{host}-ROS{ros_version}-{arch}/  # Router-specific backup directories
│       ├── {identity}-{ros_version}-{arch}-{timestamp}.backup  # Binary backup
│       ├── {identity}-{ros_version}-{arch}-{timestamp}.rsc     # Plaintext export
│       └── {identity}-{ros_version}-{arch}-{timestamp}.INFO.txt # Router info
├── bootstrap_router.py             # Router setup utility
├── config/                         # Configuration files
│   ├── global.json                 # Global settings (user generated)
│   ├── global.json.sample          # Sample global settings
│   ├── targets.json                # Router definitions (user generated)
│   └── targets.json.sample         # Sample router definitions
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

## Details setup instructions

For detailed setup instructions and configuration guide, see:
- [Setup Guide](doc/SETUP.md): Comprehensive configuration and usage documentation
- [Bootstrap Tool](doc/BOOTSTRAP.md): Guide for initial router setup and configuration

## Quick Start

1. Ensure Python 3.6 or higher is installed

2. Set up Python virtual environment (recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Create configuration files from samples
   ```bash
   cp config/global.json.sample config/global.json
   cp config/targets.json.sample config/targets.json
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

## Configuration Parameters

### Global Configuration (global.json)

Configuration options are organized into several categories:

#### Backup Settings
| Parameter | Type | Default | Overridable | Description |
|-----------|------|---------|-------------|-------------|
| `backup_path` | string | "backups" | No | Base directory for storing all router backups |
| `backup_retention_days` | integer | -1 | Yes | Days to keep backups (-1 for infinite retention) |
| `backup_password` | string | - | Yes | Default password for encrypted backups |

#### Performance Settings
| Parameter | Type | Default | Overridable | Description |
|-----------|------|---------|-------------|-------------|
| `max_concurrent_backups` | integer | 1 | No | Maximum number of concurrent backups |
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

### Router Configuration (targets.json)

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
| `backup_password` | string | - | global.json | Override global backup password |
| `backup_retention_days` | integer | - | global.json | Override global backup retention period |
| `ssh_args` | object | - | global.json | Override global SSH arguments |

The following parameters can be overridden from global.json:
- `backup_password`: Set a router-specific backup password
- `backup_retention_days`: Set a router-specific retention period
- `ssh_args`: Override any SSH connection parameters for this router

Example configuration:
```json
{
    "backup_path": "/path/to/backup/directory",
    "backup_password": "default-backup-password",
    "ssh_user": "admin",
    "targets": [
        {
            "name": "Router1",
            "host": "192.168.1.1",
            "ssh_port": 22,
            "ssh_user": "admin",
            "private_key": "/path/to/ssh/key",
            "backup_password": "router-specific-password",
            "encrypted": true,
            "enable_binary_backup": true,
            "enable_plaintext_backup": true,
            "keep_binary_backup": false,
            "keep_plaintext_backup": false
        }
    ]
}
```

## Core Modules

The application is now organized into core modules for better maintainability:

- **backup_operations.py**: Manages backup operations
- **notifications.py**: Handles notification system
- **router_info.py**: Handles gathering and formatting router information
- **ssh_utils.py**: Manages SSH connections and operations

## File Naming Format

All backup files follow a consistent naming format that includes essential router information:

- **Directory Structure**: `{identity}-{host}-ROS{ros_version}-{arch}/`
  - Example: `MYR1-192.168.1.1-ROS7.16.2-x86_64/`

- **Binary Backups**: `{identity}-{ros_version}-{arch}-{timestamp}.backup`
  - Example: `MYR1-7.16.2-x86_64-02012025-164736.backup`

- **Plaintext Exports**: `{identity}-{ros_version}-{arch}-{timestamp}.rsc`
  - Example: `MYR1-7.16.2-x86_64-02012025-164736.rsc`

- **Info Files**: `{identity}-{ros_version}-{arch}-{timestamp}.INFO.txt`
  - Example: `MYR1-7.16.2-x86_64-02012025-164736.INFO.txt`

Where:
- `{identity}`: Router's identity name
- `{host}`: Router's IP address or hostname (only in directory name)
- `{ros_version}`: RouterOS version (without "stable" suffix)
- `{arch}`: Router's architecture
- `{timestamp}`: Backup timestamp in DDMMYYYY-HHMMSS format

This naming scheme ensures:
- Consistent format across all backup types
- No spaces in filenames
- All relevant router information included
- Clear file type identification through extensions
- Easy sorting and filtering of backups

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.