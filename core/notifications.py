"""
Notifications system for RouterOS backup operations.
"""

import smtplib
from email.message import EmailMessage
from typing import List, Dict
import logging

class Notifications:
    def __init__(self, enabled: bool, notify_on_failed: bool, notify_on_success: bool, smtp_config: Dict):
        """
        Initialize the Notifications system.

        Args:
            enabled (bool): Global toggle to enable or disable notifications.
            notify_on_failed (bool): Enable notifications for failed backups.
            notify_on_success (bool): Enable notifications for successful backups.
            smtp_config (Dict): SMTP configuration dictionary.
        """
        self.enabled = enabled
        self.notify_on_failed = notify_on_failed
        self.notify_on_success = notify_on_success
        self.smtp_config = smtp_config
        self.logger = logging.getLogger(__name__)

    def send_email(self, subject: str, body: str, attachments: List[str] = None):
        """
        Send an email using SMTP.

        Args:
            subject (str): Email subject.
            body (str): Email body.
            attachments (List[str], optional): List of file paths to attach.
        """
        if not self.enabled:
            return

        if not self.smtp_config.get("enabled", False):
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
                        file_name = file_path.split('/')[-1]
                        msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)
                except Exception as e:
                    self.logger.error(f"Failed to attach {file_path}: {e}")

        try:
            if self.smtp_config.get("use_ssl", False):
                server = smtplib.SMTP_SSL(self.smtp_config.get("host", ""), self.smtp_config.get("port", 465))
            else:
                server = smtplib.SMTP(self.smtp_config.get("host", ""), self.smtp_config.get("port", 587))
                if self.smtp_config.get("use_tls", False):
                    server.starttls()

            server.login(self.smtp_config.get("username", ""), self.smtp_config.get("password", ""))
            server.send_message(msg)
            server.quit()
            self.logger.info(f"Email notification sent: {subject}")
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")

    def notify_backup(self, router: str, ip: str, success: bool, log_entries: List[str]):
        """
        Send a notification email based on backup result.

        Args:
            router (str): Router name.
            ip (str): Router IP address.
            success (bool): Whether the backup was successful.
            log_entries (List[str]): Relevant log entries to include.
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
