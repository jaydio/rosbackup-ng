# Setup Guide

## Prerequisites

- Python 3.6 or higher
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
   - Update global settings in `config/global.yaml`
   - Add your routers to `config/targets.yaml`

## Running Backups

Execute the backup script:
```bash
python3 rosbackup.py
```

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
