# RouterOS Bootstrap Tool

A utility for automating the setup of backup users on RouterOS devices. This tool creates a dedicated user account with appropriate permissions and configures SSH key-based authentication for secure, password-less backups.

## Features

- **Automated User Creation**: Creates a dedicated backup user with specified permissions
- **SSH Key Management**: Installs public keys for password-less authentication
- **Flexible Authentication**: Supports both password and key-based authentication for setup
- **Secure Password Handling**: Option to generate random passwords or use specified ones
- **Interactive Mode**: Can prompt for passwords instead of command-line input
- **Colored Logging**: Clear visual feedback with color-coded status messages

## Prerequisites

- Python 3.6 or higher
- RouterOS device with SSH access enabled
- Administrative access to the RouterOS device
- SSH public key for the backup user

## Usage

### Basic Usage

```bash
python3 bootstrap_router.py --ip <router_ip> --backup-user-public-key <path_to_public_key>
```

### Authentication Methods

#### 1. Interactive Password Authentication

Most secure method for production use. The SSH password is entered interactively and never stored in command history or visible in process list.

```bash
python3 bootstrap_router.py \
    --ip 192.168.88.1 \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

Sample output:
```
Enter password for SSH user 'admin': ********
[INFO] SSH connection established with 192.168.88.1:22
[INFO] Router identity: MYROUTER
[INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
[INFO] No backup user password provided. A random password has been generated.
[INFO] User 'rosbackup' created successfully with group 'full'
[INFO] SSH public key installed for user 'rosbackup'
[INFO] Backup user 'rosbackup' is set up successfully on router 192.168.88.1
[INFO] SSH connection closed.
```

#### 2. Command-Line Password Authentication

Useful for scripting and automation where interactive input isn't possible. Note that the password will be visible in command history and process list, so use with caution in production environments.

```bash
python3 bootstrap_router.py \
    --ip 192.168.88.1 \
    --ssh-user admin \
    --ssh-user-password yourpassword \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

Sample output:
```
[INFO] SSH connection established with 192.168.88.1:22
[INFO] Router identity: MYROUTER
[WARNING] Using password on command line is not recommended for production use
[INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
[INFO] No backup user password provided. A random password has been generated.
[INFO] User 'rosbackup' created successfully with group 'full'
[INFO] SSH public key installed for user 'rosbackup'
[INFO] Backup user 'rosbackup' is set up successfully on router 192.168.88.1
[INFO] SSH connection closed.
```

#### 3. Key-Based Authentication

Recommended method for automation and scripted deployments. Requires pre-configured SSH key access for the admin user but provides the best security for automated scenarios.

```bash
python3 bootstrap_router.py \
    --ip 192.168.88.1 \
    --ssh-user admin \
    --ssh-user-private-key ~/.ssh/id_rsa \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

Sample output:
```
[INFO] SSH connection established with 192.168.88.1:22 using key-based authentication
[INFO] Router identity: MYROUTER
[INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
[INFO] No backup user password provided. A random password has been generated.
[INFO] User 'rosbackup' created successfully with group 'full'
[INFO] SSH public key installed for user 'rosbackup'
[INFO] Backup user 'rosbackup' is set up successfully on router 192.168.88.1
[INFO] SSH connection closed.
```

### Advanced Options

#### Custom Port and User Group

For routers with non-standard SSH ports or when specific user group permissions are required. The 'full' group is recommended as it ensures all backup types will function correctly.

```bash
python3 bootstrap_router.py \
    --ip 192.168.88.1 \
    --ssh-port 2222 \
    --backup-user rosbackup \
    --backup-user-group full \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

Sample output:
```
Enter password for SSH user 'admin': ********
[INFO] SSH connection established with 192.168.88.1:2222
[INFO] Router identity: MYROUTER
[INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
[INFO] No backup user password provided. A random password has been generated.
[INFO] User 'rosbackup' created successfully with group 'full'
[INFO] SSH public key installed for user 'rosbackup'
[INFO] Backup user 'rosbackup' is set up successfully on router 192.168.88.1
[INFO] SSH connection closed.
```

#### Display Generated Credentials

When you need to view and store the generated backup user credentials during bootstrap. Important: Store these credentials securely as they won't be shown again. Usually this option is not required for production use when SSH key-based authentication is used.

```bash
python3 bootstrap_router.py \
    --ip 192.168.88.1 \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub \
    --show-backup-credentials
```

Sample output:
```
Enter password for SSH user 'admin': ********
[INFO] SSH connection established with 192.168.88.1:22
[INFO] Router identity: MYROUTER
[INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
[INFO] No backup user password provided. A random password has been generated.
[INFO] User 'rosbackup' created successfully with group 'full'
[INFO] SSH public key installed for user 'rosbackup'
[INFO] Backup user 'rosbackup' is set up successfully on router 192.168.88.1

Backup User Credentials:
Username: rosbackup
Password: Xj9#mK2$pL5vN8@qR3wS

[INFO] SSH connection closed.
```

#### Enable File Logging

Useful for auditing, troubleshooting, or maintaining operation records. The log file will contain all operations except sensitive data like passwords and keys.

```bash
python3 bootstrap_router.py \
    --ip 192.168.88.1 \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub \
    --log-file ./bootstrap.log
```

Sample output:
```
Enter password for SSH user 'admin': ********
[INFO] Logging to file: ./bootstrap.log
[INFO] SSH connection established with 192.168.88.1:22
[INFO] Router identity: MYROUTER
[INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
[INFO] No backup user password provided. A random password has been generated.
[INFO] User 'rosbackup' created successfully with group 'full'
[INFO] SSH public key installed for user 'rosbackup'
[INFO] Backup user 'rosbackup' is set up successfully on router 192.168.88.1
[INFO] SSH connection closed.
```

## Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--ip` | Yes | - | RouterOS device IP address |
| `--ssh-port` | No | 22 | SSH port number |
| `--ssh-user` | No | admin | Username for initial SSH connection |
| `--ssh-user-password` | No | - | Password for SSH user (will prompt if not provided) |
| `--ssh-user-private-key` | No | - | Private key path for SSH user authentication |
| `--backup-user` | No | rosbackup | Username to create for backups |
| `--backup-user-password` | No | - | Password for backup user (random if not provided) |
| `--backup-user-public-key` | Yes | - | Public key path for backup user authentication |
| `--backup-user-group` | No | full | RouterOS user group for backup user (must have write permission for binary backups) |
| `--show-backup-credentials` | No | false | Display backup user credentials after setup |
| `--log-file` | No | - | Path to log file (console only if not provided) |
| `--no-color` | No | false | Disable colored output |

## Command Line Options

```
Usage: bootstrap_router.py [OPTIONS]

Required Options:
  --ip IP                      IP address of the target RouterOS device
  --backup-user-public-key PATH  Path to SSH public key for backup user

Authentication Options (one required):
  --ssh-user-password PASSWORD   Password for existing SSH user
  --ssh-user-private-key PATH    Path to SSH private key for existing user

Optional Settings:
  --ssh-user USER               Existing SSH username [default: admin]
  --ssh-port PORT               SSH port [default: 22]
  --backup-user USER            Username to create [default: rosbackup]
  --backup-user-password PASS   Password for backup user [default: random]
  --backup-user-group GROUP     User group for backup user [default: full]
  --show-backup-credentials     Show backup user credentials after setup
  --log-file PATH              Path to log file [default: no file logging]
  --no-color                   Disable colored output
```

### Examples

1. Basic usage with password authentication:
```bash
python3 bootstrap_router.py --ip 192.168.1.1 \
    --ssh-user admin --ssh-user-password adminpass \
    --backup-user-public-key /path/to/backup_key.pub
```

2. Using SSH key authentication and custom backup user:
```bash
python3 bootstrap_router.py --ip 192.168.1.1 \
    --ssh-user admin --ssh-user-private-key /path/to/admin_key \
    --backup-user mybackup --backup-user-public-key /path/to/backup_key.pub \
    --backup-user-group read
```

3. With logging and no colored output:
```bash
python3 bootstrap_router.py --ip 192.168.1.1 \
    --backup-user-public-key /path/to/backup_key.pub \
    --log-file bootstrap.log --no-color
```

## Security Notes

1. The backup user is created with the specified group permissions (default: full)
   > **Note**: The user group MUST have write permission for binary backups to work. The 'full' group is recommended as it ensures all backup types will function correctly.
2. SSH keys are recommended over password authentication
3. Generated passwords are 24 characters long with mixed case, numbers, and symbols
4. Sensitive information is only displayed when --show-backup-credentials is used
5. Private keys and passwords are never logged to files

## Troubleshooting

### SSH Connection Failed
- Verify SSH service is enabled on RouterOS
- Check IP address and port number
- Ensure admin credentials are correct
- Verify network connectivity

### Permission Denied
- Verify admin user has sufficient privileges
- Check if the user group exists
- Ensure private key permissions are correct (0600)

### Public Key Installation Failed
- Verify the public key file exists and is readable
- Check the public key format is valid
- Ensure sufficient disk space on RouterOS

For detailed configuration options and parameters, refer to README.md
