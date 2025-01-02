### **SETUP.md for `rosbackup.py`**

# RouterOS Backup Script

`rosbackup.py` is a Python-based script designed to automate the backup process for multiple RouterOS devices. The script supports plaintext and binary backups, backup retention management, and parallel execution for efficient processing.

## Prerequisites

- Python 3.6 or higher.
- `paramiko` and `scp` libraries for SSH and file transfer functionality.
- Access to RouterOS devices via SSH with an appropriate user account for backups.

## Installation

### 1. Clone or Download the Repository

```
git clone <repository_url>
cd <repository_directory>
```

### 2. Set Up a Virtual Environment (Optional but Recommended)

```
python3 -m venv env
source env/bin/activate
```

### 3. Install Dependencies

```
pip install -r requirements.txt
```

Ensure that `paramiko` and `scp` are installed correctly.

## Configuration

### 1. `global.json`
This file contains global settings for the script:
```json
{
  "log_file": "./rosbackup.log",
  "log_level": "INFO",
  "backup_path_parent": "./backups",
  "backup_password": "YourSecureBackupPassword",
  "ssh_args": {
    "look_for_keys": false,
    "allow_agent": false
  },
  "parallel_execution": true,
  "max_parallel_backups": 5,
  "log_retention_days": 90,
  "backup_retention_days": 30,
  "notifications_enabled": false,
  "notify_on_failed_backups": true,
  "notify_on_successful_backups": false,
  "smtp": {
    "host": "smtp.example.com",
    "port": 587,
    "username": "user@example.com",
    "password": "securepassword",
    "use_tls": true
  }
}
```

### 2. `targets.json`
This file lists the routers to back up:
```json
{
  "routers": [
    {
      "name": "MYR1",
      "ip_address": "192.168.100.225",
      "ssh_port": 22,
      "ssh_user": "backup",
      "private_key": "./ssh-keys/private/id_rsa_rosbackup",
      "encrypted": true,
      "backup_password": "RouterSpecificPassword",
      "backup_retention_days": 15,
      "keep_binary_backup": false,
      "enable_binary_backup": true,
      "enable_plaintext_backup": true,
      "enabled": true
    }
  ]
}
```

## Usage

### Command Syntax
```bash
python3 rosbackup.py
```

### Required Configuration Files
- `config/global.json`
- `config/targets.json`

### Optional Parameters
You can modify `global.json` or `targets.json` to customize:
- Backup retention
- SSH settings
- Parallel execution
- Notifications

## Features

### 1. Backup Types
- **Plaintext Backup:** Exports router configuration to a `.rsc` file.
- **Binary Backup:** Creates a device-specific backup for quick restoration.

### 2. Parallel Execution
Execute multiple backups simultaneously for improved performance.

### 3. Backup Retention
Manage backup storage by retaining backups only for a specified number of days.

### 4. Notifications
Receive email notifications for backup results (failed or successful).

### 5. Logging
- Console logging with color-coded messages for `INFO`, `WARNING`, and `ERROR`.
- File logging (if enabled in `global.json`).

## Examples

### 1. Sequential Backups
Disable parallel execution in `global.json`:
```json
"parallel_execution": false
```

Run the script:
```bash
python3 rosbackup.py
```

### 2. Parallel Backups
Enable parallel execution and set the maximum number of parallel backups:
```json
"parallel_execution": true,
"max_parallel_backups": 5
```

Run the script:
```bash
python3 rosbackup.py
```

---

## Sample Output

### Console Output
```plaintext
2025-01-02 05:55:02 [INFO] Starting backup for router 'MYR1' at 192.168.100.225
2025-01-02 05:55:02 [INFO] SSH connection established with 192.168.100.225:22 using key-based authentication, cipher aes128-ctr, and MAC hmac-sha2-256
2025-01-02 05:55:03 [INFO] Saved plaintext backup to MYR1-192.168.100.225-ROS7.16.2-x86_64-01022025.rsc
2025-01-02 05:55:05 [INFO] Binary backup file MYR1-192.168.100.225-ROS7.16.2-x86_64-01022025.backup exists on the router.
2025-01-02 05:55:05 [INFO] Downloaded MYR1-192.168.100.225-ROS7.16.2-x86_64-01022025.backup
2025-01-02 05:55:05 [INFO] Removed remote binary backup file MYR1-192.168.100.225-ROS7.16.2-x86_64-01022025.backup
2025-01-02 05:55:05 [INFO] Backup completed for router 'MYR1' at 192.168.100.225
```

---

## Troubleshooting

### Common Errors

#### `SSH connection failed`
- Verify SSH credentials.
- Ensure the correct SSH port is specified in `targets.json`.

#### `Binary backup file does not exist`
- Ensure the backup user has write permissions.
- Verify that `/system backup save` is functional on the RouterOS device.

#### `Configuration files missing`
Ensure `global.json` and `targets.json` are correctly placed in the `config/` directory.

---

# RouterOS Backup User Bootstrap Script

`bootstrap_router.py` is a script designed to automate the process of creating a backup user on a RouterOS device, setting up secure access, and installing an SSH public key for non-interactive authentication. 

## Prerequisites

- Python 3.6 or higher.
- `paramiko` library for SSH functionality.
- A RouterOS device with SSH enabled.
- SSH credentials for a user with privileges to manage accounts and SSH keys on the device.

---

## Installation

### 1. Clone or Download the Repository
```bash
git clone <repository_url>
cd <repository_directory>
```

### 2. Set Up a Virtual Environment (Optional but Recommended)
```bash
python3 -m venv env
source env/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

Ensure that `paramiko` is installed correctly.

---

## Usage

### Command Syntax
```bash
python3 bootstrap_router.py --ip <ROUTER_IP> [OPTIONS]
```

### Required Parameters
```text
--ip                    IP address of the RouterOS device.
--backup-user-public-key  Path to the SSH public key to install for the backup user.
```

### Optional Parameters
```text
--ssh-user               SSH username (default: "admin").
--ssh-user-password      SSH password for the specified SSH user.
--ssh-user-private-key   Path to the private SSH key for the SSH user.
--ssh-port               SSH port for the connection (default: 22).
--backup-user            Backup username to create (default: "rosbackup").
--backup-user-password   Password for the backup user. If not specified, a random password will be generated.
--backup-user-group      User group for the backup user. Must have 'write' policy (default: "full").
--show-backup-credentials Print the backup user's credentials after setup.
--log-file               Path to the log file. If not specified, no file logging will be performed.
```

---

## Examples

### 1. Password-Based Authentication
```bash
python3 bootstrap_router.py --ip 192.168.100.225 --ssh-user admin --ssh-user-password adminpass \
    --backup-user rosbackup --backup-user-public-key /path/to/public_key.pub --show-backup-credentials
```

### 2. Key-Based Authentication
```bash
python3 bootstrap_router.py --ip 192.168.100.225 --ssh-user admin --ssh-user-private-key /path/to/private_key.pem \
    --backup-user rosbackup --backup-user-public-key /path/to/public_key.pub
```

### 3. Specify Custom SSH Port
```bash
python3 bootstrap_router.py --ip 192.168.100.225 --ssh-port 8022 --ssh-user admin \
    --ssh-user-password adminpass --backup-user-public-key /path/to/public_key.pub
```

---

## Features

### Random Password Generation
If `--backup-user-password` is not specified, the script will generate a random 24-character alphanumeric password for the backup user.

### SSH Authentication
The script supports both password-based and key-based SSH authentication.

### Router Identity Detection
The script retrieves the router’s identity and includes it in log outputs.

### Logging
- Console logging with color-coded output for `INFO`, `WARNING`, and `ERROR` messages.
- File logging (if `--log-file` is specified).

---

## Sample Output

### Console Output
```plaintext
2025-01-02 05:44:13 [INFO] SSH connection established with 192.168.100.225:22 using password-based authentication, cipher aes128-ctr, and MAC hmac-sha2-256
2025-01-02 05:44:13 [INFO] Attempting to create backup user on router 'MYR4' at 192.168.100.225
2025-01-02 05:44:13 [INFO] User 'rosbackup' created successfully with group 'full'.
2025-01-02 05:44:13 [INFO] SSH public key installed for user 'rosbackup'.
2025-01-02 05:44:13 [INFO] Backup user 'rosbackup' is set up successfully on router 192.168.100.225.
2025-01-02 05:44:13 [INFO] SSH connection closed.
```

---

## Troubleshooting

### Common Errors

#### `SSH connection failed`
Ensure:
- SSH is enabled on the RouterOS device.
- The correct SSH port is specified (default is 22).
- The provided credentials are valid.

#### `Failed to read public key`
Verify:
- The path to the public key is correct.
- The file exists and is readable.

---

## License

This script is provided under the MIT License. See the `LICENSE` file for more details.
```
