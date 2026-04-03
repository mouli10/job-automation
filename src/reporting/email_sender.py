import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path
from src.config import GMAIL_USER, GMAIL_PASSWORD

logger = logging.getLogger(__name__)


def send_email(subject: str, body: str, recipient: str = None):
    """Generic email sender for alerts, warnings, and notifications."""
    if not recipient:
        recipient = GMAIL_USER

    if not GMAIL_USER or not GMAIL_PASSWORD:
        logger.warning("Gmail credentials not configured. Skipping email.")
        return

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = recipient
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email sent: '{subject}' → {recipient}")
    except Exception as e:
        logger.error(f"Failed to send email '{subject}': {e}")


def send_daily_report(filepath: str, recipient: str = None):
    """Sends the daily Excel job report as an email attachment."""
    if not recipient:
        recipient = GMAIL_USER

    if not GMAIL_USER or not GMAIL_PASSWORD:
        logger.warning("Gmail credentials not configured. Skipping report email.")
        return

    path = Path(filepath)
    if not path.exists():
        logger.error(f"Report file not found: {filepath}")
        return

    today = datetime.now().strftime('%B %d, %Y')
    msg = EmailMessage()
    msg['Subject'] = f"🎯 Daily Job Matches Report — {today}"
    msg['From'] = GMAIL_USER
    msg['To'] = recipient
    msg.set_content(
        f"Hi,\n\n"
        f"Your daily job matches report for {today} is attached.\n\n"
        f"The report includes the top matching jobs scored against your resumes, "
        f"sorted by ATS score. Optimized resume links are included where applicable.\n\n"
        f"Good luck with your applications!\n\n"
        f"— AI Job Pipeline 🤖"
    )

    with open(path, 'rb') as f:
        file_data = f.read()

    msg.add_attachment(
        file_data,
        maintype='application',
        subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename=path.name
    )

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        logger.info(f"✅ Daily report sent to {recipient}: {path.name}")
    except Exception as e:
        logger.error(f"Failed to send daily report: {e}")


def send_weekly_trends_report(chart_path: str, ranked_keywords: list, window_days: int = 7, recipient: str = None):
    """
    Emails the weekly trends chart.
    - If chart_path is a PNG → embeds it inline directly in the email body (visible in Gmail instantly).
    - Also attaches the interactive HTML version if it exists alongside the PNG.
    """
    if not recipient:
        recipient = GMAIL_USER

    if not GMAIL_USER or not GMAIL_PASSWORD:
        logger.warning("Gmail credentials not configured. Skipping weekly trends email.")
        return

    path = Path(chart_path)
    if not path.exists():
        logger.error(f"Trends chart file not found: {chart_path}")
        return

    today      = datetime.now().strftime('%B %d, %Y')
    week_label = f"Last {window_days} Days"
    is_png     = path.suffix.lower() == ".png"

    # Build keyword table rows
    rows_html = ""
    for i, (kw, cnt) in enumerate(ranked_keywords[:20], 1):
        bg    = "#f0fdf4" if i % 2 == 0 else "#ffffff"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        rows_html += (
            f'<tr style="background:{bg};">'
            f'<td style="padding:8px 12px;font-weight:bold;color:#64748b;">{medal}</td>'
            f'<td style="padding:8px 12px;font-weight:600;color:#1e293b;">{kw}</td>'
            f'<td style="padding:8px 12px;color:#475569;">{cnt}</td>'
            f"</tr>"
        )

    chart_img_tag = (
        '<img src="cid:trendsChart" style="width:100%;max-width:860px;border-radius:8px;margin:20px 0;" alt="Trends Chart"/>'
        if is_png else
        '<p style="color:#64748b;font-style:italic;">📎 Interactive chart attached — open the HTML file in Chrome for full interactivity.</p>'
    )

    html_body = f"""
    <html><body style="font-family:Inter,Arial,sans-serif;background:#f8fafc;padding:20px;">
      <div style="max-width:900px;margin:0 auto;background:#fff;border-radius:12px;
                  box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">
        <div style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:30px 40px;">
          <h1 style="color:#fff;margin:0;font-size:24px;">📊 Weekly Market Trends</h1>
          <p style="color:#bfdbfe;margin:8px 0 0;">{week_label} · Delivered {today}</p>
        </div>
        <div style="padding:30px 40px;">
          <p style="color:#475569;">Top skills and tools demanded across all scraped job descriptions this week.
          Use this to spot gaps and prioritise what to add to your resume.</p>

          {chart_img_tag}

          <table style="width:100%;border-collapse:collapse;margin-top:16px;">
            <thead>
              <tr style="background:#1e3a5f;color:#fff;">
                <th style="padding:10px 12px;text-align:left;">Rank</th>
                <th style="padding:10px 12px;text-align:left;">Keyword / Tool</th>
                <th style="padding:10px 12px;text-align:left;">Frequency</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
      </div>
    </body></html>
    """

    import email.mime.multipart as mp
    import email.mime.text as mt
    import email.mime.image as mi
    import email.mime.base as mb
    import email.encoders as enc

    # Build multipart/related so the CID image reference resolves inside the HTML
    msg_root = mp.MIMEMultipart("related")
    msg_root["Subject"] = f"📊 Weekly Job Market Trends — {today}"
    msg_root["From"]    = GMAIL_USER
    msg_root["To"]      = recipient

    msg_alt = mp.MIMEMultipart("alternative")
    msg_alt.attach(mt.MIMEText(html_body, "html"))
    msg_root.attach(msg_alt)

    # Embed PNG inline
    if is_png:
        with open(path, "rb") as img_file:
            img_part = mi.MIMEImage(img_file.read(), _subtype="png")
        img_part.add_header("Content-ID", "<trendsChart>")
        img_part.add_header("Content-Disposition", "inline", filename=path.name)
        msg_root.attach(img_part)

    # Note: HTML file is saved locally in data/reports/ but NOT attached to email
    # to prevent Gmail from auto-previewing it and showing a duplicate chart.

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg_root)
        logger.info(f"✅ Weekly Trends report sent to {recipient} (inline chart: {is_png})")
    except Exception as e:
        logger.error(f"Failed to send weekly trends email: {e}")

