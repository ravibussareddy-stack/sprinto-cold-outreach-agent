"""Step 7 - send via Gmail SMTP. To: is always config.TO_ADDRESS (case rule)."""
import smtplib
from email.message import EmailMessage

from . import config


def send(domain, contact, subject, body):
    msg = EmailMessage()
    msg["From"] = f"{config.SENDER_NAME} <{config.GMAIL_ADDRESS or config.TO_ADDRESS}>"
    msg["To"] = config.TO_ADDRESS                      # hardcoded: never the real prospect
    msg["Subject"] = subject
    msg["X-Intended-Recipient"] = f"{contact['name']} <{contact.get('email') or 'unknown'}>"
    msg.set_content(body)

    if config.DRY_RUN or config.OFFLINE:
        config.OUTBOX_DIR.mkdir(exist_ok=True)
        path = config.OUTBOX_DIR / f"{domain}.eml"
        path.write_bytes(bytes(msg))
        return {"status": "dry_run", "path": str(path)}

    if not (config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD):
        raise RuntimeError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env to send")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
        s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        s.send_message(msg)
    return {"status": "sent", "to": config.TO_ADDRESS}
