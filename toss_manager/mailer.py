"""Small SMTP adapter; account workflows remain usable when SMTP is unconfigured."""

from email.message import EmailMessage
import smtplib

from .config import MailSettings


def send_account_token(*, recipient: str, token: str, purpose: str) -> bool:
    settings = MailSettings.from_env()
    if not settings.configured:
        return False
    label = "이메일 인증" if purpose == "verify" else "비밀번호 재설정"
    message = EmailMessage()
    message["Subject"] = f"[Porto] {label} 코드"
    message["From"] = settings.sender
    message["To"] = recipient
    message.set_content(
        f"Porto {label} 코드입니다.\n\n{token}\n\n"
        "이 코드는 30분 동안 한 번만 사용할 수 있습니다. 요청하지 않았다면 무시하세요."
    )
    with smtplib.SMTP(settings.host, settings.port, timeout=10) as smtp:
        if settings.use_tls:
            smtp.starttls()
        if settings.username:
            smtp.login(settings.username, settings.password)
        smtp.send_message(message)
    return True
