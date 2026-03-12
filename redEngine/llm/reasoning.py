import os
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-2.5-flash")

async def explainRediscovery(idea, chunks):

    context = "\n".join([c["text"][:300] for c in chunks[:3]])

    prompt = f"""
User Idea:
{idea}

Possible related historical text:
{context}

Answer in **3 short sentences max**:
1. Is this idea already discovered?
2. What earlier concept is it related to?
3. When or where it appeared.
"""

    response = model.generate_content(prompt)

    text = response.text

    return text.strip()