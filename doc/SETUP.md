# Setup Guide

## Prerequisites

- Python 3.13.1 or higher
- RouterOS devices with SSH access enabled
- SSH key pair for authentication

## Installation

1. Clone the repository and enter directory
    ```bash
   git clone https://git.pnty.app/jd/rosbackup-ng.git
   cd rosbackup-ng
   ```

2. Set up Python virtual environment (recommended)
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install dependencies
    ```bash
    pip install -r requirements.txt
    ```

4. Enable command completion (optional but recommended)
    ```bash
    # For current session
    source scripts/rosbackup-ng-completion.bash

    # For permanent setup (choose one based on your shell):
    # Bash
    echo "source $(pwd)/scripts/rosbackup-ng-completion.bash" >> ~/.bashrc

    # Zsh
    echo "source $(pwd)/scripts/rosbackup-ng-completion.bash" >> ~/.zshrc
    ```

## Initial Configuration

1. Create configuration files from samples
   ```bash
   cp config/global.yaml.sample config/global.yaml
   cp config/targets.yaml.sample config/targets.yaml
   ```

2. Set up SSH keys (choose one option):
   
   a. Create symbolic links to existing keys:
   ```bash
   ln -s ~/.ssh/id_rsa ssh-keys/private/id_rosbackup
   ln -s ~/.ssh/id_rsa.pub ssh-keys/public/id_rosbackup.pub
   ```
   
   b. Generate new key pair:
   ```bash
   ssh-keygen -t rsa -b 4096 -f ssh-keys/private/id_rosbackup -C "rosbackup"
   ```

3. Configure RouterOS devices for backup:
   
   Option 1: Use `bootstrap_router.py` to automatically configure devices (recommended)
   ```bash
   # Basic usage - will prompt for SSH password
   python3 bootstrap_router.py --host 192.168.88.1 --backup-user-public-key ssh-keys/public/id_rosbackup.pub

   # With password authentication
   python3 bootstrap_router.py --host 192.168.88.1 \
       --ssh-user admin --ssh-user-password yourpassword \
       --backup-user-public-key ssh-keys/public/id_rosbackup.pub

   # With SSH key authentication
   python3 bootstrap_router.py --host 192.168.88.1 \
       --ssh-user admin --ssh-user-private-key ~/.ssh/id_rsa \
       --backup-user-public-key ssh-keys/public/id_rosbackup.pub

   # Show generated credentials
   python3 bootstrap_router.py --host 192.168.88.1 \
       --backup-user-public-key ssh-keys/public/id_rosbackup.pub \
       --show-backup-credentials
   ```
   
   See [BOOTSTRAP.md](BOOTSTRAP.md) for detailed usage instructions.

   Option 2: Manually set up SSH keys and user permissions
   ```bash
   # 1. Log into RouterOS device and create backup user
   /user add name=rosbackup group=full password=<secure-password>

   # 2. Add SSH public key for the backup user
   /user ssh-keys import public-key-file=id_rosbackup.pub user=rosbackup

   # 3. Verify SSH key was imported
   /user ssh-keys print
   ```

4. Edit configuration files:
   - Update global settings in `config/global.yaml`:
     ```yaml
     # Backup Settings
     backup_path_parent: backups     # Base directory for backups
     backup_retention_days: 90       # Days to keep backups (-1 for infinite)
     backup_password: your-password  # Default password for encrypted backups

     # SSH Settings
     ssh:
       user: rosbackup               # Default SSH username
       timeout: 30                   # Connection timeout in seconds
       auth_timeout: 30              # Authentication timeout in seconds
       known_hosts_file: null        # Optional: Path to known_hosts file
       add_target_host_key: true     # Whether to auto-add target host keys
       args:
         look_for_keys: false        # Search for keys in ~/.ssh/
         allow_agent: false          # Allow ssh-agent connections

     # Logging Settings
     log_file_enabled: false         # Enable logging to file
     log_file: ./rosbackup.log       # Log file path
     log_level: INFO                 # Log level
     log_retention_days: 90          # Days to keep logs
     ```
   
   - Add your routers to `config/targets.yaml`:
     ```yaml
     routers:
       - name: ROUTER1                    # Required: Unique identifier
         enabled: true                    # Optional: Enable/disable this router
         host: 192.168.88.1               # Required: Router IP or hostname
         ssh_port: 22                     # Optional: SSH port (default: 22)
         ssh_user: rosbackup              # Optional: Override global SSH user
         private_key: ./ssh-keys/private/id_rosbackup  # Required: SSH private key
         encrypted: false                 # Optional: Enable backup encryption
         backup_password: MyPassword      # Optional: Override global password
         backup_retention_days: 90        # Optional: Override global retention
         enable_binary_backup: true       # Optional: Enable binary backup
         enable_plaintext_backup: true    # Optional: Enable plaintext backup
         keep_binary_backup: false        # Optional: Keep backup on router
         keep_plaintext_backup: false     # Optional: Keep export on router
     ```

## Backup File Organization

The backup files are organized in a structured hierarchy:

```
backups/
└── {identity}-{host}-ROS{ros_version}-{arch}/    # Router-specific directory
    ├── {identity}-{ros_version}-{arch}-{timestamp}.backup    # Binary backup
    ├── {identity}-{ros_version}-{arch}-{timestamp}.rsc       # Plaintext export
    └── {identity}-{ros_version}-{arch}-{timestamp}.INFO.txt  # Router info
```

### File Naming Convention

- **Directory Name**: `{identity}-{host}-ROS{ros_version}-{arch}`
  - `identity`: Router's name from config (e.g., "ROUTER1")
  - `host`: IP address or hostname (e.g., "192.168.88.1")
  - `ros_version`: RouterOS version (e.g., "7.10.2")
  - `arch`: Router architecture (e.g., "arm", "x86_64")

- **File Names**: `{identity}-{ros_version}-{arch}-{timestamp}.{ext}`
  - `identity`: Same as directory
  - `ros_version`: Same as directory
  - `arch`: Same as directory
  - `timestamp`: Backup time (format: DDMMYYYY-HHMMSS)
  - `ext`: File extension:
    - `.backup`: Binary backup file
    - `.rsc`: Plaintext configuration export
    - `.INFO.txt`: Router information file

Example:
```
backups/
└── ROUTER1-192.168.88.1-ROS7.10.2-arm/
    ├── ROUTER1-7.10.2-arm-02012025-143022.backup
    ├── ROUTER1-7.10.2-arm-02012025-143022.rsc
    └── ROUTER1-7.10.2-arm-02012025-143022.INFO.txt
```

## Running Backups

First, create and activate the Python virtual environment if you haven't already:

```bash
# Create virtual environment (only needed once)
python3 -m venv venv

# Activate the virtual environment (needed each time you start a new shell)
source venv/bin/activate
```

Execute the backup script (both methods work):
```bash
./rosbackup.py
# or
python3 rosbackup.py
```

## SSH Configuration

The tool provides several SSH configuration options in `global.yaml`:

```yaml
ssh:
  user: rosbackup               # Default SSH username
  timeout: 30                   # Connection timeout in seconds
  auth_timeout: 30              # Authentication timeout in seconds
  known_hosts_file: null        # Optional: Path to known_hosts file
  add_target_host_key: true     # Whether to auto-add target host keys
  args:
    look_for_keys: false        # Search for keys in ~/.ssh/
    allow_agent: false          # Allow ssh-agent connections
```

These settings can be overridden per router in `targets.yaml` using the `ssh_args` parameter.

## Troubleshooting

### SSH Connection Issues
- Verify SSH credentials and key permissions (0600 for private keys)
- Ensure RouterOS SSH service is enabled
- Check if the backup user has sufficient permissions

### Backup Failures
- Verify write permissions in backup directories
- Check if `/system backup save` works on RouterOS device
- Ensure sufficient disk space on both router and backup server

### Configuration Issues
- Verify YAML syntax in config files
- Check file paths are correct and accessible
- Ensure all required fields are properly set

For detailed configuration options and parameters, refer to README.md
