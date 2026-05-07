import os
import asyncio
import logging
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)

_configured_key = None


def _ensure_configured():
    """
    Load API key from .env and configure Gemini.
    Reloads every call to support live key changes.
    """
    global _configured_key

    load_dotenv(dotenv_path=_ROOT / ".env", override=True)

    key = os.getenv("GEMINI_API_KEY")

    if not key:
        raise EnvironmentError(
            f"GEMINI_API_KEY not found. Looked in: {_ROOT / '.env'}"
        )

    # Debug (can remove later)
    print("ENV PATH:", _ROOT / ".env")
    print("API KEY:", key)

    if key != _configured_key:
        genai.configure(api_key=key)
        _configured_key = key
        logger.info("Gemini API key (re)configured.")


async def explainRediscovery(idea, chunks):
    _ensure_configured()

    # Stable model (important fix)
    model = genai.GenerativeModel("models/gemini-flash-lite-latest")

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
        "IMPORTANT — Your response MUST begin with the standard name of this concept, "
        "followed by a colon, then the explanation. "
        "Example format: 'Photosynthesis: The process by which plants...'\n\n"
        "Write a natural, flowing explanation (3-5 paragraphs) that covers:\n"
        "- What this concept is called and how it is commonly understood\n"
        "- Its origins — who discovered or described it, and when and where it appeared\n"
        "- How it has evolved or been rediscovered over time\n"
        "- Any closely related concepts, fields, or ideas it connects to\n"
        "- Why it is significant or how it is used today\n\n"
        "Write as if explaining to a curious person. Do not use bullet points or numbered lists.\n"
        "Do not say 'Based on the sources' or 'According to the text'."
    )

    for attempt in range(2):
        try:
            # Fix: run blocking call safely
            response = await asyncio.to_thread(
                model.generate_content, prompt
            )

            # Fix: correct response parsing
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception as parse_error:
                print("Parsing Error:", parse_error)
                text = None

            # Debug (can remove later)
            print("RAW GEMINI OUTPUT:", text)

            if not text:
                return f"This concept relates to: {idea}. Further analysis could not be generated at this time."

            return text.strip()

        except Exception as e:
            err = str(e)

            # Zero quota case
            if "quota_limit_value" in err and '"0"' in err:
                logger.error(
                    "Gemini API key has ZERO quota. Get a new key from https://aistudio.google.com/apikey"
                )
                break

            # Rate limit retry
            if "429" in err and attempt < 1:
                logger.warning("Gemini 429, retrying in 5s…")
                await asyncio.sleep(5)
                continue

            # Show real error
            print("GEMINI ERROR:", e)
            logger.error("Gemini error for idea '%s': %s", idea, e)
            break

    return f"An explanation could not be generated at this time. The concept '{idea}' was recorded for future reference."