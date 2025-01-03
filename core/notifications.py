"""
Notifications system for RouterOS backup operations.

This module provides email notification capabilities for backup operations,
supporting both success and failure notifications with configurable SMTP settings.
"""

import smtplib
from email.message import EmailMessage
from typing import List, Dict, Optional, TypedDict
import logging
from pathlib import Path


class SMTPConfig(TypedDict):
    """SMTP configuration dictionary type definition."""
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    from_email: str
    to_emails: List[str]
    use_ssl: bool
    use_tls: bool


class NotificationConfig(TypedDict):
    """Notification configuration dictionary type definition."""
    enabled: bool
    notify_on_failed: bool
    notify_on_success: bool
    smtp: SMTPConfig


class Notifications:
    """
    Manages email notifications for backup operations.
    
    This class handles sending email notifications for backup operations,
    with support for success/failure notifications and file attachments.
    
    Attributes:
        enabled (bool): Global toggle for notifications
        notify_on_failed (bool): Send notifications for failed backups
        notify_on_success (bool): Send notifications for successful backups
        smtp_config (SMTPConfig): SMTP server configuration
        logger (logging.Logger): Logger instance for this class
    """

    def __init__(self, enabled: bool, notify_on_failed: bool, notify_on_success: bool, smtp_config: SMTPConfig) -> None:
        """
        Initialize the Notifications system.

        Args:
            enabled: Global toggle to enable/disable notifications
            notify_on_failed: Enable notifications for failed backups
            notify_on_success: Enable notifications for successful backups
            smtp_config: SMTP configuration including:
                - enabled: Enable/disable SMTP
                - host: SMTP server hostname
                - port: SMTP server port
                - username: SMTP authentication username
                - password: SMTP authentication password
                - from_email: Sender email address
                - to_emails: List of recipient email addresses
                - use_ssl: Use SSL for connection
                - use_tls: Use STARTTLS for connection
        """
        self.enabled = enabled
        self.notify_on_failed = notify_on_failed
        self.notify_on_success = notify_on_success
        self.smtp_config = smtp_config
        self.logger = logging.getLogger(__name__)

    def send_email(self, subject: str, body: str, attachments: Optional[List[Path]] = None) -> None:
        """
        Send an email using SMTP.

        Sends an email with optional attachments using the configured SMTP server.
        Supports both SSL and TLS connections.

        Args:
            subject: Email subject line
            body: Email body content
            attachments: Optional list of file paths to attach

        Error Handling:
            - Logs attachment failures individually
            - Logs SMTP connection and authentication errors
            - Continues operation if individual attachments fail
        """
        if not self.enabled or not self.smtp_config.get("enabled", False):
            return

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = self.smtp_config.get("from_email", "")
        msg['To'] = ', '.join(self.smtp_config.get("to_emails", []))
        msg.set_content(body)

        # Attach files if any
        if attachments:
            for file_path in attachments:
                try:
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        file_name = file_path.name
                        msg.add_attachment(file_data, maintype='application', 
                                        subtype='octet-stream', filename=file_name)
                except Exception as e:
                    self.logger.error(f"Failed to attach {file_path}: {e}")

        try:
            if self.smtp_config.get("use_ssl", False):
                server = smtplib.SMTP_SSL(self.smtp_config.get("host", ""), 
                                        self.smtp_config.get("port", 465))
            else:
                server = smtplib.SMTP(self.smtp_config.get("host", ""), 
                                    self.smtp_config.get("port", 587))
                if self.smtp_config.get("use_tls", False):
                    server.starttls()

            server.login(self.smtp_config.get("username", ""), 
                        self.smtp_config.get("password", ""))
            server.send_message(msg)
            server.quit()
            self.logger.info(f"Email notification sent: {subject}")
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")

    def notify_backup(self, router: str, ip: str, success: bool, log_entries: List[str]) -> None:
        """
        Send a notification email based on backup result.

        Sends an email notification for backup operations based on success/failure
        and notification preferences.

        Args:
            router: Name of the router
            ip: Router's IP address
            success: Whether the backup was successful
            log_entries: List of relevant log entries to include

        Note:
            - Only sends if notifications are enabled globally
            - Respects notify_on_success and notify_on_failed settings
            - Includes log entries in the email body if available
        """
        if not self.enabled:
            return

        if success and not self.notify_on_success:
            return

        if not success and not self.notify_on_failed:
            return

        subject = f"Backup {'Successful' if success else 'Failed'} for {router} ({ip})"
        body = f"Backup {'completed successfully' if success else 'failed'} for router '{router}' at {ip}.\n\n"

        if log_entries:
            body += "Log Entries:\n"
            body += "\n".join(log_entries)
        else:
            body += "No additional log information available."

        self.logger.debug(f"Preparing to send notification email for {router}")
        self.send_email(subject, body)
