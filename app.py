import streamlit as st
from gmail_auth import authenticate_new_user, get_gmail_service_from_token
from groq import Groq
from dotenv import load_dotenv
import os
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def mask_email(email):
    try:
        local, domain = email.split('@')
        masked = local[:2] + '*' * (len(local) - 2)
        return f"{masked}@{domain}"
    except:
        return "***@***.com"

# ----------------------- HELPER FUNCTIONS -----------------------
def send_email(service, to, subject, body, thread_id=None, message_id=None):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = "Re: " + subject
    if message_id:
        message['In-Reply-To'] = message_id
        message['References'] = message_id
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    payload = {'raw': raw}
    if thread_id:
        payload['threadId'] = thread_id
    service.users().messages().send(
        userId='me',
        body=payload
    ).execute()

def notify_admin(name, email, reason):
    try:
        msg = MIMEMultipart()
        msg['From'] = os.getenv("NOTIFY_EMAIL")
        msg['To'] = os.getenv("NOTIFY_EMAIL")
        msg['Subject'] = f"New Access Request from {name}"
        body = f"Name: {name}\nEmail: {email}\nReason: {reason}"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(os.getenv("NOTIFY_EMAIL"), os.getenv("NOTIFY_PASSWORD"))
        server.sendmail(os.getenv("NOTIFY_EMAIL"), os.getenv("NOTIFY_EMAIL"), msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Email notify error: {e}")

# ----------------------- SESSION STATE INIT -----------------------
if 'emails' not in st.session_state:
    st.session_state.emails = []
if 'reply' not in st.session_state:
    st.session_state.reply = ""
if 'labels' not in st.session_state:
    st.session_state.labels = []
if 'token' not in st.session_state:
    st.session_state.token = None
if 'service' not in st.session_state:
    st.session_state.service = None
if 'analytics' not in st.session_state:
    st.session_state.analytics = {
        'total_users': 0,
        'total_summarized': 0,
        'feedback': []
    }
if 'request_sent' not in st.session_state:
    st.session_state.request_sent = False
if 'paste_summary' not in st.session_state:
    st.session_state.paste_summary = ""

st.title("📧 Email Summarizer Agent")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔗 Connect Gmail",
    "📋 Paste Email",
    "📝 Request Access",
    "📊 Analytics"
])

# ======================= TAB 1 — CONNECT GMAIL =======================
with tab1:
    if st.session_state.token is None:
        st.info("👋 Connect your Gmail account to get started!")
        if st.button("🔗 Connect Gmail Account"):
            with st.spinner("Opening Google login..."):
                try:
                    creds = authenticate_new_user()
                    st.session_state.token = json.loads(creds.to_json())
                    st.session_state.service = get_gmail_service_from_token(st.session_state.token)
                    st.session_state.analytics['total_users'] += 1
                    st.success("✅ Gmail connected!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    else:
        service = st.session_state.service

        if st.button("🔌 Disconnect Account"):
            st.session_state.token = None
            st.session_state.service = None
            st.session_state.emails = []
            st.session_state.reply = ""
            st.session_state.labels = []
            st.success("✅ Account disconnected!")
            st.rerun()

        st.success("✅ Gmail Connected!")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Load Labels"):
                with st.spinner("Loading labels..."):
                    results = service.users().labels().list(userId='me').execute()
                    st.session_state.labels = [
                        {'id': l['id'], 'name': l['name']}
                        for l in results.get('labels', [])
                    ]
                    st.success(f"Loaded {len(st.session_state.labels)} labels!")
        with col2:
            new_label = st.text_input("Create new label:")
            if st.button("Create Label"):
                if new_label:
                    try:
                        with st.spinner("Creating label..."):
                            service.users().labels().create(
                                userId='me',
                                body={'name': new_label}
                            ).execute()
                            st.success(f"✅ Label '{new_label}' created!")
                            results = service.users().labels().list(userId='me').execute()
                            st.session_state.labels = [
                                {'id': l['id'], 'name': l['name']}
                                for l in results.get('labels', [])
                            ]
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                else:
                    st.warning("Please enter a label name!")

        max_emails = st.slider("How many emails?", 1, 20, 5)
        subject_filter = st.text_input("Filter by subject keyword (optional)")
        sender_filter = st.text_input("Filter by sender email (optional)")

        if st.button("Fetch Emails"):
            query = ""
            if subject_filter:
                query += f"subject:{subject_filter} "
            if sender_filter:
                query += f"from:{sender_filter} "
            with st.spinner("Fetching emails..."):
                results = service.users().messages().list(
                    userId='me',
                    maxResults=max_emails,
                    labelIds=['INBOX'],
                    q=query.strip() if query else None
                ).execute()
                st.session_state.emails = []
                for message in results.get('messages', []):
                    msg = service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='full'
                    ).execute()
                    headers = msg['payload']['headers']
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                    snippet = msg['snippet']
                    message_id_header = next((h['value'] for h in headers if h['name'] == 'Message-ID'), None)
                    st.session_state.emails.append({
                        'id': message['id'],
                        'thread_id': msg['threadId'],
                        'message_id': message_id_header,
                        'subject': subject,
                        'snippet': snippet,
                        'sender': sender
                    })
            st.success(f"Fetched {len(st.session_state.emails)} emails!")

        if st.session_state.emails:
            filtered = [
                e for e in st.session_state.emails
                if subject_filter.lower() in e.get('subject', '').lower()
                and sender_filter.lower() in e.get('sender', '').lower()
            ]

            if filtered:
                selected_subject = st.selectbox("Select an email:", [e['subject'] for e in filtered])
                selected_email = next(e for e in filtered if e['subject'] == selected_subject)
                st.write("👤 From:", selected_email.get('sender', 'Unknown'))
                st.write("🔑 Email ID:", selected_email['id'])

                if st.button("Summarize Selected Email"):
                    with st.spinner("Summarizing..."):
                        response = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "You are an email assistant. Summarize in 1 line and tell me if any action is required."},
                                {"role": "user", "content": f"Subject: {selected_email['subject']}\nEmail: {selected_email['snippet']}"}
                            ],
                            model="llama-3.3-70b-versatile",
                        )
                    summary = response.choices[0].message.content
                    st.session_state.analytics['total_summarized'] += 1
                    st.write("📧 Subject:", selected_email['subject'])
                    st.write("🤖 Summary:", summary)

                if st.button("Generate AI Reply"):
                    with st.spinner("Generating reply..."):
                        reply = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "You are an email assistant. Write a professional reply to this email in 2-3 lines."},
                                {"role": "user", "content": f"Subject: {selected_email['subject']}\nEmail: {selected_email['snippet']}"}
                            ],
                            model="llama-3.3-70b-versatile",
                        )
                    st.session_state.reply = reply.choices[0].message.content

                if st.session_state.reply:
                    st.text_area("✏️ Edit Reply Before Sending:", value=st.session_state.reply, key="edited_reply")
                    if st.button("Send Reply"):
                        with st.spinner("Sending..."):
                            try:
                                edited = st.session_state.get("edited_reply", st.session_state.reply)
                                send_email(
                                    service,
                                    to=selected_email['sender'],
                                    subject=selected_email['subject'],
                                    body=edited,
                                    thread_id=selected_email.get('thread_id'),
                                    message_id=selected_email.get('message_id')
                                )
                                st.success("✅ Reply sent successfully!")
                                st.session_state.reply = ""
                            except Exception as e:
                                st.error(f"❌ Error sending: {e}")

                if st.session_state.labels:
                    label_names = [l['name'] for l in st.session_state.labels]
                    selected_label = st.selectbox("Move to label:", label_names)
                    if st.button("Move to Label"):
                        with st.spinner("Moving email..."):
                            try:
                                label_id = next(l['id'] for l in st.session_state.labels if l['name'] == selected_label)
                                service.users().messages().modify(
                                    userId='me',
                                    id=selected_email['id'],
                                    body={
                                        'addLabelIds': [label_id],
                                        'removeLabelIds': ['INBOX']
                                    }
                                ).execute()
                                st.success(f"✅ Moved to {selected_label}!")
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
            else:
                st.write("No emails match your filter!")

# ======================= TAB 2 — PASTE EMAIL =======================
with tab2:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 Paste Email Content")
    with col2:
        if st.button("🔄 Reset"):
            st.session_state.paste_summary = ""
            st.rerun()

    pasted_email = st.text_area("Paste your email content here:", height=200)

    st.subheader("🎨 Summary Style")
    summary_style = st.radio(
        "Choose your summary style:",
        [
            "2-3 Lines Max",
            "Bullet Points",
            "Action Items Only",
            "Custom Style"
        ],
        key="summary_style"
    )

    custom_style = ""
    if summary_style == "Custom Style":
            custom_style = st.text_input("Describe your style:", placeholder="e.g. Summarize like a lawyer, be very formal")
    if summary_style == "2-3 Lines Max":
        style_prompt = "Summarize this email in 2-3 lines max. Be concise and clear."
    elif summary_style == "Bullet Points":
        style_prompt = "Summarize this email in bullet points. Max 4 bullets."
    elif summary_style == "Action Items Only":
        style_prompt = "Extract only the action items from this email as a bullet list. What needs to be done?"
    elif summary_style == "Custom Style":
        style_prompt = custom_style if custom_style else "Summarize this email clearly."

    
    if st.button("Summarize Pasted Email"):
        if pasted_email:
            with st.spinner("Summarizing..."):
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": f"You are an email assistant. {style_prompt}"},
                        {"role": "user", "content": f"Summarize this email: {pasted_email}"}
                    ],
                    model="llama-3.3-70b-versatile",
                )
            st.session_state.paste_summary = response.choices[0].message.content
            st.session_state.analytics['total_summarized'] += 1
        else:
            st.warning("Please paste some email content first!")

    if st.session_state.paste_summary:
        st.success("🤖 Summary:")
        st.write(st.session_state.paste_summary)
        st.markdown("---")
        st.subheader("💬 How was the summary?")
        
        col1, col2 = st.columns(2)
        with col1:
            user_name = st.text_input("Your name (optional):", key="paste_name")
        with col2:
            user_profession = st.text_input("Your profession (optional):", key="paste_profession")
        
        rating = st.slider("Rate the summary (1-5):", 1, 5, 3, key="paste_rating")
        feedback_text = st.text_input("Any comments? (optional)", key="paste_feedback")

        if st.button("Submit Feedback"):
            st.session_state.analytics['feedback'].append({
                'rating': rating,
                'comment': feedback_text,
                'name': user_name if user_name else 'Anonymous',
                'profession': user_profession if user_profession else 'Not specified',
                'time': datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            st.session_state.paste_summary = ""
            st.success("✅ Thanks for your feedback!")
            st.rerun()

# ======================= TAB 3 — REQUEST ACCESS =======================
with tab3:
    st.subheader("📝 Request Gmail Access")
    st.write("Enter your details and we'll add you as a tester!")

    if st.session_state.request_sent:
        st.success("✅ Request submitted successfully! We'll get back to you soon.")
        st.info("💡 Once approved you'll be able to use the Connect Gmail tab!")
        if st.button("Submit Another Request"):
            st.session_state.request_sent = False
            st.rerun()
    else:
        request_name = st.text_input("Your name:")
        request_email = st.text_input("Your Gmail address:")
        request_reason = st.text_area("Why do you want to test? (optional)")

        if st.button("Submit Request"):
            if request_email and request_name:
                notify_admin(request_name, request_email, request_reason)
                st.session_state.analytics['feedback'].append({
                    'type': 'access_request',
                    'email': request_email,
                    'name': request_name,
                    'reason': request_reason,
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                st.session_state.request_sent = True
                st.rerun()
            else:
                st.warning("Please enter your name and Gmail address!")

# ======================= TAB 4 — ANALYTICS =======================
with tab4:
    st.subheader("📊 App Analytics")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👥 Total Users", st.session_state.analytics['total_users'])
    with col2:
        st.metric("📧 Emails Summarized", st.session_state.analytics['total_summarized'])
    with col3:
        feedback_list = [f for f in st.session_state.analytics['feedback'] if 'rating' in f]
        avg_rating = round(sum(f['rating'] for f in feedback_list) / len(feedback_list), 1) if feedback_list else 0
        st.metric("⭐ Avg Rating", avg_rating)

    if feedback_list:
        st.markdown("---")
        st.subheader("💬 User Feedback")
        for f in feedback_list:
            name = f.get('name', 'Anonymous')
            profession = f.get('profession', 'Not specified')
            st.write(f"⭐ {f['rating']}/5 — {f.get('comment', '')} — 👤 {name} ({profession}) — {f['time']}")

    requests = [f for f in st.session_state.analytics['feedback'] if f.get('type') == 'access_request']
    if requests:
        st.markdown("---")
        st.subheader("📬 Access Requests")
        for r in requests:
            masked = mask_email(r['email'])
            st.write(f"📧 {masked} — {r['name']} — {r['time']}")
            if r['reason']:
                st.write(f"   Reason: {r['reason']}")
