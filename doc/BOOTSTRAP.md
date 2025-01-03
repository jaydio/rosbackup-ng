# RouterOS Bootstrap Tool

A utility for automating the setup of backup users on RouterOS devices. This tool creates a dedicated user account with appropriate permissions and configures SSH key-based authentication for secure, password-less backups.

## Features

- **Automated User Creation**: Creates a dedicated backup user with specified permissions
- **SSH Key Management**: Installs public keys for password-less authentication
- **Flexible Authentication**: Supports both password and key-based authentication for setup
- **Secure Password Handling**: Option to generate random passwords or use specified ones
- **Interactive Mode**: Prompts for password if neither password nor key is provided
- **Colored Logging**: Clear visual feedback with color-coded status messages
- **Command Completion**: Bash completion support for all options and file paths

## Prerequisites

- Python 3.6 or higher
- RouterOS device with SSH access enabled
- Administrative access to the RouterOS device
- SSH public key for the backup user

## Configuration

The bootstrap tool will use SSH settings from `config/global.yaml` if present. This includes:
- Connection timeouts (default: 30 seconds)
- Authentication timeouts (default: 30 seconds)
- Known hosts handling:
  - `known_hosts_file`: Path to SSH known_hosts file
  - `add_target_host_key`: Whether to automatically add target host keys
- SSH arguments:
  - `look_for_keys`: Search for discoverable private key files
  - `allow_agent`: Allow connecting to ssh-agent

If no global configuration is found, it will use default settings:
```yaml
ssh:
  timeout: 30
  auth_timeout: 30
  known_hosts_file: null
  add_target_host_key: true
  args:
    look_for_keys: false
    allow_agent: false
```

## Usage

### Enable Command Completion

For easier command-line usage, enable bash completion:

```bash
source scripts/rosbackup-completion.bash
```

This provides tab completion for all options and relevant file paths.

### Basic Usage

```bash
python3 bootstrap_router.py --host <router_ip> --backup-user-public-key <path_to_public_key>
```

### Authentication Methods

#### 1. Interactive Password Authentication

Most secure method for production use. The SSH password is entered interactively when neither password nor private key is provided.

```bash
python3 bootstrap_router.py \
    --host 192.168.88.1 \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

Sample output:
```
Enter password for user 'admin': ********
2025-01-02 22:46:06 [INFO] Connected (version 2.0, client ROSSSH)
2025-01-02 22:46:06 [INFO] Authentication (password) successful!
2025-01-02 22:46:06 [INFO] SSH connection established with 192.168.88.1:22 using password-based authentication
2025-01-02 22:46:06 [INFO] Attempting to create backup user on router 'MYROUTER' at 192.168.88.1
2025-01-02 22:46:06 [INFO] No backup user password provided. A random password will be generated.
2025-01-02 22:46:06 [INFO] A random password with 24 characters has been generated for the backup user.
2025-01-02 22:46:06 [INFO] User 'backup' created successfully with group 'full'
2025-01-02 22:46:06 [INFO] SSH public key installed for user 'backup'.
2025-01-02 22:46:06 [INFO] Backup user 'backup' is set up successfully on router 192.168.88.1.
2025-01-02 22:46:06 [INFO] SSH connection closed.
2025-01-02 22:46:06 [INFO] Bootstrap process completed.
```

#### 2. Command-Line Password Authentication

Useful for scripting and automation where interactive input isn't possible. Note that the password will be visible in command history and process list, so use with caution in production environments.

```bash
python3 bootstrap_router.py \
    --host 192.168.88.1 \
    --ssh-user admin \
    --ssh-user-password yourpassword \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

#### 3. Key-Based Authentication

Recommended method for automation and scripted deployments. Requires pre-configured SSH key access for the admin user but provides the best security for automated scenarios.

```bash
python3 bootstrap_router.py \
    --host 192.168.88.1 \
    --ssh-user admin \
    --ssh-user-private-key ~/.ssh/id_rsa \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub
```

### Additional Options

#### Show Backup User Credentials

When you need to view and store the generated backup user credentials during bootstrap. Important: Store these credentials securely.

```bash
python3 bootstrap_router.py \
    --host 192.168.88.1 \
    --backup-user-public-key ssh-keys/public/id_rosbackup.pub \
    --show-backup-credentials
```

Sample output with credentials:
```
...
Backup User Credentials:
Username: backup
Password: Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8
...
```

## Command-Line Options

| Short | Long | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `-H` | `--host` | - | Yes | RouterOS device IP address or hostname |
| `-k` | `--backup-user-public-key` | - | Yes | Public key file for backup user authentication |
| `-u` | `--ssh-user` | admin | No* | SSH username for initial connection |
| `-P` | `--ssh-user-password` | - | No* | SSH password for initial connection |
| `-i` | `--ssh-user-private-key` | - | No* | SSH private key for initial connection |
| `-p` | `--ssh-port` | 22 | No | SSH port number |
| `-b` | `--backup-user` | backup | No | Username for backup account |
| `-B` | `--backup-user-password` | - | No | Password for backup user (auto-generated if not set) |
| `-g` | `--backup-user-group` | full | No | User group for backup user |
| `-s` | `--show-backup-credentials` | false | No | Display generated backup user credentials |
| `-l` | `--log-file` | - | No | Path to log file (no file logging if not set) |
| `-n` | `--no-color` | false | No | Disable colored output |
| `-d` | `--dry-run` | false | No | Show what would be done without making changes |

\* Either `-P`/`--ssh-user-password` or `-i`/`--ssh-user-private-key` must be provided, or the script will prompt for password.

## Important Notes

1. The backup user is created with the specified group permissions (default: full)
   > **Note**: The user group MUST have write permission for binary backups to work. The 'full' group is recommended as it ensures all backup types will function correctly.
2. SSH keys are recommended over password authentication
3. Generated passwords are 24 characters long with mixed case letters and numbers
4. When a user already exists, the script will skip user creation and attempt to install the SSH key
5. The script will prompt for password if neither `--ssh-user-password` nor `--ssh-user-private-key` is provided
6. Private keys and passwords are never logged to files

## Troubleshooting

### SSH Connection Failed

1. Verify SSH service is enabled on the router:
   ```
   /ip service print
   ```
   Enable if needed:
   ```
   /ip service enable ssh
   ```

2. Check SSH port (default: 22):
   ```
   /ip service get ssh port
   ```

3. Verify firewall rules allow SSH access

4. Test SSH connectivity:
   ```bash
   ssh admin@192.168.1.1 -p 22
   ```

### Authentication Failed

1. Verify username and password/key are correct
2. Check if the user has sufficient permissions
3. Ensure SSH keys are in the correct format
4. Try interactive password authentication first
