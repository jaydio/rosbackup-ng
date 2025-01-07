# Command Line Reference

## rosbackup.py

The main backup utility for RouterOS devices.

```bash
./rosbackup.py [OPTIONS]
```

| Short | Long | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `-c` | `--config-dir` | `config` | No | Directory containing configuration files |
| `-l` | `--log-file` | None | No | Override log file path |
| `-L` | `--log-level` | `INFO` | No | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `-n` | `--no-color` | False | No | Disable colored output |
| `-d` | `--dry-run` | False | No | Simulate operations without making changes |
| `-p` | `--no-parallel` | False | No | Disable parallel execution |
| `-m` | `--max-parallel` | None | No | Override maximum parallel backups |
| `-t` | `--target` | None | No | Run backup on specific target only |
| `-b` | `--progress-bar` | False | No | Show progress bar during parallel execution (disables scrolling output) |
| `-x` | `--compose-style` | False | No | Show Docker Compose style output instead of log messages |

## bootstrap_router.py

Utility for configuring RouterOS devices for automated backups.

```bash
./bootstrap_router.py [OPTIONS]
```

| Short | Long | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `-H` | `--host` | None | Yes | RouterOS device IP address or hostname |
| `-k` | `--backup-user-public-key` | None | Yes | Public key file for backup user authentication |
| `-P` | `--ssh-user-password` | None | No* | SSH password for initial connection |
| `-i` | `--ssh-user-private-key` | None | No* | SSH private key for initial connection |
| `-u` | `--ssh-user` | `admin` | No | SSH username for initial connection |
| `-p` | `--ssh-port` | `22` | No | SSH port number |
| `-b` | `--backup-user` | `rosbackup` | No | Username for backup account |
| `-B` | `--backup-user-password` | Auto-generated | No | Password for backup user |
| `-g` | `--backup-user-group` | `full` | No | User group for backup user |
| `-s` | `--show-backup-credentials` | False | No | Display generated backup user credentials |
| `-l` | `--log-file` | None | No | Path to log file |
| `-n` | `--no-color` | False | No | Disable colored output |
| `-d` | `--dry-run` | False | No | Show what would be done without making changes |
| `-f` | `--force` | False | No | Force user creation even if the user already exists |

\* Either `-P` or `-i` must be provided for authentication
