import os
import time
import logging
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=_ROOT / ".env")

_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    raise EnvironmentError(f"GEMINI_API_KEY not found. Looked in: {_ROOT / '.env'}")

genai.configure(api_key=_api_key)

model = genai.GenerativeModel("gemini-2.5-flash")

logger = logging.getLogger(__name__)


async def explainRediscovery(idea, chunks):

    if chunks:
        context = "\n\n".join([
            f"[Source: {c.get('title', 'Unknown')}]\n{c['text'][:500]}"
            for c in chunks[:5]
        ])
        source_instruction = (
            "Here is relevant information found from historical sources, "
            "research papers, and encyclopedias:\n\n"
            + context
            + "\n\nUse this information to enrich your explanation where relevant."
        )
    else:
        source_instruction = (
            "No external sources were retrieved. "
            "Use your own knowledge to explain this concept thoroughly."
        )

    prompt = (
        "You are a knowledgeable assistant explaining concepts in clear, natural language.\n\n"
        f'A user submitted this idea or concept: "{idea}"\n\n'
        f"{source_instruction}\n\n"
        "Write a natural, flowing explanation (3-5 paragraphs) that covers:\n"
        "- What this concept is called and how it is commonly understood\n"
        "- Its origins — who discovered or described it, and when and where it appeared\n"
        "- How it has evolved or been rediscovered over time\n"
        "- Any closely related concepts, fields, or ideas it connects to\n"
        "- Why it is significant or how it is used today\n\n"
        "Write as if explaining to a curious person. Do not use bullet points or numbered lists.\n"
        "Start directly with the concept explanation. "
        "Do not say 'Based on the sources' or 'According to the text'."
    )

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            text = response.text
            if not text:
                return f"This concept relates to: {idea}. Further analysis could not be generated at this time."
            return text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err and attempt < 2:
                wait = 15 * (attempt + 1)
                logger.warning("Gemini 429, retrying in %ds…", wait)
                time.sleep(wait)
                continue
            logger.error("Gemini error for idea '%s': %s", idea, e)
            return f"An explanation could not be generated at this time. The concept '{idea}' was recorded for future reference."