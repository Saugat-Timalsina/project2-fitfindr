"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )

    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     e.g., "vintage graphic tee".
        size: Size string to filter by, or None to skip size filtering.
        max_price: Maximum price, or None to skip price filtering.

    Returns:
        A list of matching listing dictionaries sorted by relevance.
        Returns [] if nothing matches.
    """
    listings = load_listings()

    if not description or description.strip() == "":
        return []

    query_words = description.lower().split()
    matches = []

    for item in listings:
        # 1. Filter by max price if provided
        if max_price is not None:
            try:
                item_price = float(item.get("price", 0))
                if item_price > float(max_price):
                    continue
            except (TypeError, ValueError):
                continue

        # 2. Filter by size if provided
        if size is not None and size.strip() != "":
            requested_size = size.lower().strip()
            item_size = str(item.get("size", "")).lower().strip()

            # This lets "M" match "M" or "S/M"
            if requested_size not in item_size:
                continue

        # 3. Build searchable text from listing fields
        searchable_text = " ".join([
            str(item.get("title", "")),
            str(item.get("description", "")),
            str(item.get("category", "")),
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
            str(item.get("brand", "")),
            str(item.get("platform", "")),
        ]).lower()

        # 4. Score listing by keyword overlap
        score = sum(1 for word in query_words if word in searchable_text)

        # 5. Keep only relevant listings
        if score > 0:
            item_copy = item.copy()
            item_copy["match_score"] = score
            matches.append(item_copy)

    # Sort by match score first, then cheaper price
    matches.sort(
        key=lambda item: (
            item.get("match_score", 0),
            -float(item.get("price", 0))
        ),
        reverse=True
    )

    return matches


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest a complete outfit.

    Args:
        new_item: A listing dict selected from search_listings().
        wardrobe: A wardrobe dict with an 'items' key.

    Returns:
        A non-empty string with an outfit suggestion.
        If the wardrobe is empty, returns general styling advice.
    """
    if not new_item:
        return "I couldn't suggest an outfit because no selected item was provided."

    wardrobe_items = wardrobe.get("items", []) if wardrobe else []

    if len(wardrobe_items) == 0:
        wardrobe_text = (
            "The user's wardrobe is empty. Give general styling advice using common basics "
            "such as jeans, sneakers, jackets, neutral pants, or simple accessories."
        )
    else:
        formatted_items = []

        for item in wardrobe_items:
            name = item.get("name", item.get("title", "Unnamed item"))
            category = item.get("category", "unknown category")
            color = item.get("color", item.get("colors", "unknown color"))
            style = item.get("style", item.get("style_tags", ""))

            formatted_items.append(
                f"- {name}: category={category}, color={color}, style={style}"
            )

        wardrobe_text = "\n".join(formatted_items)

    prompt = f"""
You are FitFindr, a secondhand fashion styling assistant.

The user is considering this thrifted item:

Title: {new_item.get("title")}
Description: {new_item.get("description")}
Category: {new_item.get("category")}
Style tags: {new_item.get("style_tags")}
Size: {new_item.get("size")}
Condition: {new_item.get("condition")}
Price: ${new_item.get("price")}
Colors: {new_item.get("colors")}
Brand: {new_item.get("brand")}
Platform: {new_item.get("platform")}

User wardrobe:
{wardrobe_text}

Task:
Suggest 1 complete outfit using the thrifted item.
If the wardrobe has items, use at least one named wardrobe piece.
If the wardrobe is empty, clearly say the wardrobe is empty and give a general outfit idea.
Make the suggestion stylish, realistic, and specific.
Keep it under 120 words.
"""

    try:
        client = _get_groq_client()

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful secondhand fashion styling assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=250,
        )

        return response.choices[0].message.content.strip()

    except Exception as error:
        return (
            "I couldn't generate a full AI outfit suggestion because the styling tool failed. "
            f"Try again after checking your API key or internet connection. Error: {error}"
        )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit: The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message.
    """
    if not outfit or outfit.strip() == "":
        return (
            "I couldn't create a fit card because the outfit suggestion was missing. "
            "Please try generating the outfit again."
        )

    if not new_item:
        return (
            "I couldn't create a fit card because the selected thrift item was missing. "
            "Please search for an item again."
        )

    prompt = f"""
You are FitFindr, a secondhand fashion caption writer.

Create a short, shareable outfit caption for this thrifted item and outfit.

Thrifted item:
Title: {new_item.get("title")}
Price: ${new_item.get("price")}
Platform: {new_item.get("platform")}
Condition: {new_item.get("condition")}
Brand: {new_item.get("brand")}
Colors: {new_item.get("colors")}

Outfit suggestion:
{outfit}

Rules:
- Write 2 to 4 short sentences.
- Sound like a real Instagram or TikTok outfit post.
- Mention the item title, price, and platform naturally once.
- Capture the outfit vibe with specific language.
- Do not sound like a product description.
- Keep it under 60 words.
"""

    try:
        client = _get_groq_client()

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You write casual, stylish, secondhand fashion captions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.95,
            max_tokens=180,
        )

        return response.choices[0].message.content.strip()

    except Exception as error:
        return (
            "I couldn't create the fit card because the caption tool failed. "
            f"Try again after checking your API key or internet connection. Error: {error}"
        )