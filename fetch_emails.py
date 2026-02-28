from gmail_auth import get_gmail_service

service = get_gmail_service()

results = service.users().messages().list(
    userId='me',
    maxResults=5,
    labelIds=['INBOX']
).execute()

messages = results.get('messages', [])
print(messages)

for message in messages:
    msg = service.users().messages().get(
        userId='me',
        id=message['id'],
        format='full'
    ).execute()
    
    # Get email subject
    headers = msg['payload']['headers']
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
    
    # Get email snippet (preview)
    snippet = msg['snippet']
    
    print(f"Subject: {subject}")
    print(f"Preview: {snippet}")
    print("---")