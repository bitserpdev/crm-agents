import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv
import os

load_dotenv()

def check_inbox():
    mail = imaplib.IMAP4_SSL(os.getenv("SMTP_HOST"), 993)
    mail.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
    
    print(f"Logged in as: {os.getenv('SMTP_USER')}")
    
    mail.select("INBOX")
    
    # List last 10 emails
    status, data = mail.search(None, "ALL")
    msg_ids = data[0].split()[-10:]  # last 10
    
    print(f"\nLast {len(msg_ids)} emails in INBOX:\n")
    
    for msg_id in reversed(msg_ids):
        status, hdr_data = mail.fetch(msg_id, "(RFC822.HEADER)")
        hdr_msg = email.message_from_bytes(hdr_data[0][1])
        
        from_ = hdr_msg.get("From", "")
        subject = hdr_msg.get("Subject", "")
        date = hdr_msg.get("Date", "")
        
        # Decode subject
        parts = decode_header(subject)
        subject_str = ""
        for part, enc in parts:
            if isinstance(part, bytes):
                subject_str += part.decode(enc or "utf-8", errors="ignore")
            else:
                subject_str += part
        
        print(f"From:    {from_}")
        print(f"Subject: {subject_str}")
        print(f"Date:    {date}")
        print("-" * 60)
    
    # Also list all folders
    print("\nAll mailbox folders:")
    status, folders = mail.list()
    for f in folders:
        print(" ", f.decode())
    
    mail.logout()

check_inbox()