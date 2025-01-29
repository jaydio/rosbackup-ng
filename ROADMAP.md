# RouterOS Backup NG Roadmap

This document outlines the planned features and improvements for future releases of RouterOS Backup NG.

## Planned Features

### 1. Notification System
- [x] E-Mail (SMTP) support (initial release)
- [ ] Channel Specific Alerting templates
- [ ] Generic webhook support
- [ ] Telegram integration
- [ ] NTFY.sh for push notifications)
- [ ] Healthchecks.io integration
- [ ] Mattermost/Slack (via webhook)
- [ ] OpsGenie integration
- [ ] PagerDuty integration
- [ ] Discord integration
- [ ] Gotify / NOTIFYRUN integration
- [ ] ... insert more notification channels ...

### 2. Backup Enhancements
- [x] Use a temporary file system (tmpfs) to store binary backup (0.5.0)
      - Instead of saving to primary storage of target (flash for most appliances)
- [ ] Integrate GIT support for plaintext backups
- [ ] Support for certificate store backup
- [ ] Automatic certificate renewal tracking

### 4. Monitoring and Reporting
- [ ] Prometheus endpoint
- [ ] Detailed backup statistics
- [ ] Performance metrics collection
- [ ] Status dashboard
- [ ] Custom report generation (PDF/E-Mail)
- [ ] Backup success rate tracking

### 5. Integration Features
- [ ] PyPI package
- [ ] Docker Image
- [ ] REST API for remote management
- [ ] Integration with monitoring systems
- [ ] Backup scheduling service (async)

### 6. User Experience
- [ ] Web-based management interface

### 7. Misc Features
- [ ] Remote restore capabilities
- [ ] Basic Remote command execution functionality
- [ ] Recovery testing tools

Missing a feature? Open an issue or send a PR :)
