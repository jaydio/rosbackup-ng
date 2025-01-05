# Filesystem Structure

```
rosbackup-ng/
├── config/                     # Configuration directory
│   ├── global.yaml             # Global settings
│   ├── global.yaml.sample      # Example global configuration
│   ├── targets.yaml            # Target definitions
│   └── targets.yaml.sample     # Example target configuration
│
├── core/                       # Core functionality modules
│   ├── __init__.py             # Module initialization
│   ├── backup_utils.py         # Backup operations
│   ├── logging_utils.py        # Logging system
│   ├── notification_utils.py   # Email notifications
│   ├── router_utils.py         # Router information gathering
│   ├── shell_utils.py          # Shell output formatting
│   ├── ssh_utils.py            # SSH connection management
│   └── time_utils.py           # Timezone handling
│
├── doc/                        # Documentation
│   ├── BOOTSTRAP.md            # Router preparation guide
│   ├── COMMAND_REFERENCE.md    # CLI options reference
│   ├── CONFIG_REFERENCE.md     # Configuration parameters
│   ├── FILESYSTEM_STRUCTURE.md # This file
│   └── SETUP.md                # Installation guide
│
├── backups/                    # Default backup storage
│   └── [target_name]/          # Per-target directories
│       ├── *.backup            # Binary backup files
│       ├── *.info              # System information
│       └── *.rsc               # Plaintext exports
│
├── ssh-keys/                   # SSH key storage
│   ├── private/                # Private keys
│   │   └── id_rosbackup        # Default key
│   └── public/                 # Public keys
│       └── id_rosbackup.pub    # Default key
│
├── rosbackup.py                # Main backup utility
├── bootstrap_router.py         # Router preparation tool
├── requirements.txt            # Python dependencies
└── README.md                   # Original documentation
```

### Directory Details

- `config/`: Contains all configuration files. Copy the .sample files to create your configurations.
  
- `core/`: Contains the modular implementation of all major features:
  - Backup operations and file management
  - Logging system with color support
  - Email notification system
  - Router information gathering
  - SSH connection handling
  - Time and timezone utilities
  
- `doc/`: Comprehensive documentation covering all aspects of the utility:
  - Installation and setup
  - Router preparation
  - Command-line options
  - Configuration parameters
  - Project structure
  
- `backups/`: Default location for backup storage, organized by target:
  - Binary backup files (.backup)
  - System information files (.info)
  - Plaintext configuration exports (.rsc)
  
- `ssh-keys/`: Recommended location for SSH key storage:
  - Private keys used for authentication
  - Public keys for router setup
