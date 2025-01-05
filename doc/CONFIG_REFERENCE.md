# Configuration Reference

## Global Configuration (global.yaml)

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `backup_path_parent` | str | `backups` | Yes | No | Parent directory for storing backups |
| `backup_retention_days` | int | `90` | No | Yes | Days to keep backups before deletion |
| `backup_password` | str | None | No | Yes | Global password for encrypted backups |
| `timezone` | str | System timezone | No | No | Timezone for timestamps (e.g., 'Europe/Berlin') |
| `parallel_execution` | bool | `true` | No | CLI | Enable parallel backup execution |
| `max_parallel_backups` | int | `5` | No | CLI | Maximum concurrent backup operations |
| `log_file_enabled` | bool | `false` | No | CLI | Enable logging to file |
| `log_file` | str | `./rosbackup.log` | No | CLI | Path to log file |
| `log_level` | str | `INFO` | No | CLI | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `log_retention_days` | int | `90` | No | No | Days to keep log files |

### SSH Settings (`ssh` section)

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `user` | str | `rosbackup` | Yes | Yes | Default SSH username |
| `timeout` | int | `5` | No | Yes | Connection timeout in seconds |
| `auth_timeout` | int | `5` | No | Yes | Authentication timeout in seconds |
| `known_hosts_file` | str | None | No | Yes | Path to known_hosts file |
| `add_target_host_key` | bool | `true` | No | Yes | Auto-add target host keys |

#### SSH Arguments (`ssh.args` section)

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `look_for_keys` | bool | `false` | No | Yes | Search for SSH keys in ~/.ssh/ |
| `allow_agent` | bool | `false` | No | Yes | Allow SSH agent forwarding |
| `compress` | bool | `true` | No | Yes | Enable SSH compression |
| `auth_timeout` | int | `5` | No | Yes | SSH auth timeout in seconds |
| `channel_timeout` | int | `5` | No | Yes | SSH channel timeout in seconds |
| `keepalive_interval` | int | `60` | No | Yes | Keepalive interval in seconds |
| `keepalive_countmax` | int | `3` | No | Yes | Max failed keepalives before disconnect |
| `disabled_algorithms` | dict | `{"pubkeys": ["rsa-sha1"]}` | No | Yes | Dict of algorithms to disable (see [here](https://docs.paramiko.org/en/stable/api/transport.html#paramiko.transport.Transport.disabled_algorithms) for details)|

### Notification Settings

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `notifications_enabled` | bool | `false` | No | No | Enable notifications globally |
| `notify_on_failed_backups` | bool | `true` | No | No | Send notifications for failures |
| `notify_on_successful_backups` | bool | `false` | No | No | Send notifications for successes |

#### SMTP/Email Settings (`smtp` section)

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `enabled` | bool | `false` | No | No | Enable SMTP notifications |
| `host` | str | None | Yes* | No | SMTP server hostname |
| `port` | int | `587` | Yes* | No | SMTP server port |
| `username` | str | None | Yes* | No | SMTP authentication username |
| `password` | str | None | Yes* | No | SMTP authentication password |
| `from_email` | str | None | Yes* | No | Sender email address |
| `to_emails` | List[str] | None | Yes* | No | List of recipient emails |
| `use_tls` | bool | `true` | No | No | Use STARTTLS |
| `use_ssl` | bool | `false` | No | No | Use SSL/TLS from start |

\* Required if SMTP is enabled

## Target Configuration (targets.yaml)

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `name` | str | None | Yes | No | Unique target identifier |
| `enabled` | bool | `true` | No | No | Enable/disable this target |
| `host` | str | None | Yes | No | Router hostname or IP |
| `backup_password` | str | Global | No | N/A | Target-specific backup password |
| `backup_retention_days` | int | Global | No | N/A | Target-specific retention period |
| `encrypted` | bool | `false` | No | No | Enable backup encryption |
| `enable_binary_backup` | bool | `true` | No | No | Create binary backup |
| `enable_plaintext_backup` | bool | `true` | No | No | Create plaintext export |
| `keep_binary_backup` | bool | `false` | No | No | Keep binary backup on router |
| `keep_plaintext_backup` | bool | `false` | No | No | Keep plaintext backup on router |

### Target SSH Settings (`ssh` section)

| Parameter | Type | Default | Required | Overridable | Description |
|-----------|------|---------|----------|-------------|-------------|
| `port` | int | `22` | No | No | SSH port number |
| `user` | str | Global | No | N/A | Target-specific SSH username |
| `private_key` | str | None | Yes | No | Path to SSH private key |
| `args` | dict | Global | No | N/A | Target-specific SSH arguments |

Notes:
- "_Overridable_" indicates if the parameter can be overridden in targets.yaml
- "_CLI_" in Overridable means the parameter can only be overridden via command-line
- Parameters marked with Global in Default inherit from global configuration
- SSH args in targets can override any args from global configuration
