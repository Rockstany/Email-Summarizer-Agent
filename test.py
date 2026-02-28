from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("API Key loaded:", client.api_key is not None)

chat_completion = client.chat.completions.create(
   messages=[
    {
        "role": "system",
        "content": "You are an email assistant. Bullet Point 1 - Always summarize emails in 1 lines max & Bullet Point 2 -> What is the emotions behind like they buy it or Asking for reply something Like . Use bullet points."
    },
    {
        "role": "user",
        "content": "Hey, just checking if you received the documents I sent over yesterday. Let me know if you have any questions or need further information. Thanks!"
    }
],
    model="llama-3.3-70b-versatile",
)

print(chat_completion.choices[0].message.content)

# System -> The Rules of the AI i will tell it do 
# User -> What give them the content and they will give you the output 
# Assistant -> The output of the AI - for memory purpose we can use it to store the output of the AI and use it in future conversations 