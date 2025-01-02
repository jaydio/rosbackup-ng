# RouterOS Backup Script (rosbackup-ng)

A robust Python-based utility for automating backups of multiple RouterOS devices via SSH. This tool supports both binary and plaintext backups, with features for backup retention management and parallel execution.

## Features

- **Multiple Backup Types**: Supports both binary (.backup) and plaintext (.rsc) backups
- **Parallel Processing**: Efficiently backs up multiple devices simultaneously
- **Backup Retention**: Automated cleanup of old backups based on configurable retention periods
- **Secure**: Uses SSH key-based authentication
- **Informative**: Generates detailed info files containing router specifications
- **Notification Support**: Integrated notification system for backup status updates
- **Color-coded Logging**: Clear visual feedback during operation

## Quick Start

1. Ensure Python 3.6 or higher is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your routers in the config directory
4. Run the script:
   ```bash
   python rosbackup.py
   ```

## Configuration Parameters

### Global Configuration (global.json)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `backup_path_parent` | string | "backups" | Base directory for storing all router backups |
| `log_file` | string | "./rosbackup.log" | Path to the log file |
| `log_level` | string | "INFO" | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `enable_file_logging` | boolean | false | Enable logging to file in addition to console |
| `log_retention_days` | integer | 90 | Number of days to keep log files |
| `ssh_user` | string | "rosbackup" | Default SSH username for router connections |
| `parallel_execution` | boolean | true | Enable parallel backup processing |
| `max_parallel_backups` | integer | 5 | Maximum number of concurrent backups |
| `backup_password` | string | - | Default password for encrypted backups |
| `backup_retention_days` | integer | 90 | Days to keep backups (-1 for infinite retention) |

### Notification System

The notification system supports multiple channels for alerting about backup status and events. Configure notification settings in the `notifications` section of `global.json`.

#### Global Notification Settings
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notifications_enabled` | boolean | false | Master switch for all notifications |
| `notify_on_failed_backups` | boolean | true | Send notifications for failed backups |
| `notify_on_successful_backups` | boolean | false | Send notifications for successful backups |

#### SMTP Email Channel
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `smtp.enabled` | boolean | false | Enable SMTP email notifications |
| `smtp.host` | string | - | SMTP server hostname |
| `smtp.port` | integer | 587 | SMTP server port |
| `smtp.username` | string | - | SMTP authentication username |
| `smtp.password` | string | - | SMTP authentication password |
| `smtp.use_tls` | boolean | true | Enable TLS encryption |
| `smtp.from_email` | string | - | Sender email address |
| `smtp.to_emails` | array | - | List of recipient email addresses |

#### Coming Soon
The following notification channels are planned for future releases:
- **Telegram**: Direct messages or group notifications via Telegram Bot API
- **ntfy**: Push notifications using the ntfy.sh service
- **Webhooks**: Custom HTTP callbacks for integration with other systems
- **Slack**: Direct messages and channel notifications
- **Mattermost**: Team communication platform integration

### Router Configuration (targets.json)

Each router in the `routers` array supports the following parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | Required | Unique identifier for the router |
| `ip_address` | string | Required | Router's IP address or hostname |
| `ssh_port` | integer | 22 | SSH port number |
| `ssh_user` | string | global | Override global SSH username |
| `private_key` | string | Required | Path to SSH private key file |
| `backup_password` | string | global | Override global backup password |
| `encrypted` | boolean | false | Enable backup encryption |
| `backup_retention_days` | integer | global | Override global retention period |
| `keep_binary_backup` | boolean | false | Keep binary backup file on router |
| `enable_binary_backup` | boolean | true | Enable binary backup creation |
| `enable_plaintext_backup` | boolean | true | Enable plaintext backup creation |
| `enabled` | boolean | true | Enable/disable this router |

Notes:
- Parameters marked with "global" default to the value specified in global.json
- Parameters marked with "Required" must be specified in the configuration
- All paths can be relative to the script directory or absolute paths

## Directory Structure

```
.
├── backups/                # Backup storage directory
│   └── [router-name]/      # Individual router backup folders
│       ├── *.backup        # Binary backup files
│       ├── *.INFO.txt      # Router information files
│       └── *.rsc           # Plaintext configuration backups
├── bootstrap_router.py     # Router initialization utility
├── config/                 # Configuration directory
│   ├── global.json         # Global settings
│   └── targets.json        # Router targets configuration
├── doc/
│   ├── SETUP.md            # Detailed setup instructions
│   └── BOOTSTRAP.md        # Bootstrap tool documentation
├── notifications.py        # Notification system implementation
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── rosbackup.py            # Main backup script
└── ssh-keys/               # SSH authentication keys
    ├── private/            # Private key storage
    └── public/             # Public key storage
```

## Requirements

- Python 3.6+
- paramiko
- scp
- RouterOS devices with SSH access enabled

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

For detailed information, see:
- [Setup Guide](doc/SETUP.md)
- [Bootstrap Tool Documentation](doc/BOOTSTRAP.md)