from gmail_auth import get_gmail_service
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

service = get_gmail_service()

results = service.users().messages().list(
    userId='me',
    maxResults=5,
    labelIds=['INBOX']
).execute()

messages = results.get('messages', [])

for message in messages:
    msg = service.users().messages().get(
        userId='me',
        id=message['id'],
        format='full'
    ).execute()

    headers = msg['payload']['headers']
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
    snippet = msg['snippet']

    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are an email assistant. Summarize in 1 line and tell me if any action is required."},
            {"role": "user", "content": f"Subject: {subject}\nEmail: {snippet}"}
        ],
        model="llama-3.3-70b-versatile",
    )

    print(f"📧 Subject: {subject}")
    print(f"🤖 Summary: {response.choices[0].message.content}")
    print("---")