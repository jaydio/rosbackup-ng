# Backup Structure

## Naming Convention

The backup files follow a standardized naming format that includes essential information about the router and backup:

- **Directory Name**: `{identity}_{host}_ROS{ros_version}_{arch}`
  - `identity`: Router's system identity (e.g., "HQ-ROUTER-01")
  - `host`: IP address or hostname (e.g., "192.168.1.1")
  - `ros_version`: RouterOS version (e.g., "7.10.2")
  - `arch`: Router architecture (e.g., "arm", "x86_64")

- **File Names**: `{identity}_{ros_version}_{arch}_{timestamp}.{ext}`
  - `identity`: Same as directory
  - `ros_version`: Same as directory
  - `arch`: Same as directory
  - `timestamp`: Backup creation time (format: MMDDYYYY-HHMMSS)
    - Uses system timezone by default
    - Can be overridden with `timezone` setting in global config
  - `ext`: File extension indicating type:
    - `.backup`: Binary backup file
    - `.rsc`: Plaintext configuration export
    - `.info`: Router information and specifications

## Directory Layout

```
backups/
├── ROUTER1_192.168.88.1_ROS7.8_x86_64/
│   ├── ROUTER1_7.8_x86_64_01052025-230427.backup
│   ├── ROUTER1_7.8_x86_64_01052025-230427.info
│   └── ROUTER1_7.8_x86_64_01052025-230427.rsc
└── ROUTER2_10.0.0.1_ROS7.7_arm64/
    ├── ROUTER2_7.7_arm64_01052025-230427.backup
    ├── ROUTER2_7.7_arm64_01052025-230427.info
    └── ROUTER2_7.7_arm64_01052025-230427.rsc
```

## File Types

### Binary Backup (.backup)
- Full system backup that can be used for complete system restore (same router model)
- Can be encrypted with a password (MikroTik proprietary)
- Contains all system settings, including:
  - Interface MAC addresses*
  - Sensitive data
  - Certificate store
  - User database

**Notes:**

- After a restore, interface MAC addresses can be reset using:
  - ```/interface/ethernet/reset-mac-address [find]```

### Plaintext Backup (.rsc)
- Human-readable script containing router configuration
- Uses RouterOS export command with following parameters:
  - `terse`: Produces single-line commands without wrapping
    - Makes output easier to process with tools like `grep`
    - Better for automated parsing and analysis
    - More consistent format across RouterOS versions
  - `show-sensitive`: Includes sensitive data like:
    - SNMP community strings
    - RADIUS secrets
    - PPP/PPTP/L2TP/SSTP/OVPN secrets
    - IPsec pre-shared keys
    - Wireguard private keys
- __<u>Does NOT include</u>__
  - Certificate store (will be added in a future version)
    - incl. certificates used by API server or IPSEC sessions (!) 
  - User database and user passwords (unsupported)
  - ZeroTier private key (unsupported)

### System Information (.info)
The `.info` files contain comprehensive system information including:

#### System Identity and Hardware
- Router identity
- RouterOS version
- Hardware model / Board name
- System ID and license level
- Serial number
- Architecture and platform
- CPU details (name, count, frequency)
- Memory usage (free/total)
- Storage information (free/total space, write sectors)

#### System Status
- System uptime
- Time and date settings
- Timezone configuration
  - Name and GMT offset
  - Auto-detection status
  - DST active status

#### Network Statistics
- IPv4/IPv6 firewall rules count
  - Filter rules
  - NAT rules
  - Mangle rules
  - Raw rules
  - Address lists
  - Active states
- Interface counts
  - Ethernet interfaces
  - Bridge interfaces
  - VLAN interfaces
  - Bonding interfaces
- DHCP services
  - IPv4/IPv6 servers
  - IPv4/IPv6 clients
  - IPv4/IPv6 relays
- Address pools
- PPP active sessions
- Queue tree items
- ARP/Neighbor entries
  - IPv4 ARP (failed/permanent/reachable)
  - IPv6 neighbors