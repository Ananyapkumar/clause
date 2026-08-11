# 1. imports — os, load_dotenv from dotenv, genai from google
import os
from dotenv import load_dotenv
from google import genai
# 2. call load_dotenv()
load_dotenv()





# 3. Model name lives in one variable so it's swappable in one place
MODEL = "gemini-3.6-flash"
# 4. EMAIL = """ ...paste the messy email here... """
EMAIL = """Subject: Re: Fwd: RE: quick q re the thing

hey — sorry for the delay, was OOO. so re: what we discussed on the call,
finance came back and they're saying the 15th doesn't work for them anymore??
i think we can push to end of month but honestly if we slip past Q3 close
we're in trouble. Priya mentioned something about the 28th but i'm not sure
if she meant this month or next.

can you confirm whether the invoice went out? i checked and i don't see it
but our system is a mess so who knows. if it did go out on the 3rd then
we're fine, if not we need to redo the PO.

also — separate thing — are we still on for the review next tues? Manish
said he'd send an invite but nothing's landed. no rush if not.

thx
-J

sent from my iphone"""
# 5. create the client, passing the key from os.environ
client = genai.Client()
# 6. build the prompt — combine your instruction with EMAIL
prompt = f"What is the sender's intent, and what dates are mentioned?\n\n{EMAIL}"
# 7. send it to the model
interaction = client.interactions.create(
    model=MODEL,
    input=prompt
)
# 8. print the result
print(interaction.output_text)