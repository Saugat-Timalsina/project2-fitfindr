"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

The agent does NOT call all tools blindly. It checks the state after each tool:
- If search_listings returns no results, it returns early.
- If search succeeds, it stores selected_item.
- Then it passes selected_item into suggest_outfit.
- Then it passes outfit_suggestion into create_fit_card.
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
        "retry_note": None,
    }


# ── simple query parser ───────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query.

    This is a simple rule-based parser. It is not perfect, but it is enough
    for the project because the goal is the agent planning loop, not perfect NLP.
    """

    original_query = query
    query_lower = query.lower()

    # Extract price from phrases like:
    # "under $30", "under 30", "below $40", "less than $25"
    max_price = None
    price_match = re.search(
        r"(?:under|below|less than)\s*\$?(\d+(?:\.\d+)?)",
        query_lower,
    )

    if price_match:
        max_price = float(price_match.group(1))

    # Extract size from phrases like:
    # "size M", "size medium", "size small"
    size = None
    size_match = re.search(
        r"size\s+(xxs|xs|s|m|l|xl|xxl|small|medium|large)",
        query_lower,
    )

    if size_match:
        size = size_match.group(1).upper()

        if size == "SMALL":
            size = "S"
        elif size == "MEDIUM":
            size = "M"
        elif size == "LARGE":
            size = "L"

    # Build a cleaner description by removing price and size phrases
    description = original_query

    description = re.sub(
        r"(?:under|below|less than)\s*\$?\d+(?:\.\d+)?",
        "",
        description,
        flags=re.IGNORECASE,
    )

    description = re.sub(
        r"size\s+(xxs|xs|s|m|l|xl|xxl|small|medium|large)",
        "",
        description,
        flags=re.IGNORECASE,
    )

    # Remove common filler phrases
    filler_phrases = [
        "i am looking for",
        "i'm looking for",
        "looking for",
        "i want",
        "find me",
        "can you find",
        "please find",
    ]

    description_lower = description.lower()

    for phrase in filler_phrases:
        description_lower = description_lower.replace(phrase, "")

    description = description_lower.strip(" .,!")

    # If parser removed too much, fall back to original query
    if not description:
        description = original_query

    return {
        "description": description,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query: Natural language user request.
        wardrobe: User's wardrobe dict.

    Returns:
        The session dict after the interaction completes.
    """

    session = _new_session(query, wardrobe)

    # Step 1: Parse the query
    parsed = _parse_query(query)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    # Step 2: Call search_listings
    results = search_listings(
        description=description,
        size=size,
        max_price=max_price,
    )

    session["search_results"] = results

    # Step 3: Stretch feature fallback retry
    # If exact size gives no results, retry without size.
    if not results and size is not None:
        retry_results = search_listings(
            description=description,
            size=None,
            max_price=max_price,
        )

        if retry_results:
            session["retry_note"] = (
                "I couldn't find results in your exact size, "
                "so I retried without the size filter."
            )
            session["search_results"] = retry_results
            results = retry_results

    # Step 4: If no results after retry, stop early
    if not results:
        session["error"] = (
            "I couldn't find any listings that match that request. "
            "Try increasing your budget, using a broader description, "
            "or removing the size filter."
        )
        return session

    # Step 5: Select top result and store it in state
    session["selected_item"] = results[0]

    # Step 6: Call suggest_outfit with selected item from state
    outfit = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=wardrobe,
    )

    session["outfit_suggestion"] = outfit

    # Step 7: If outfit suggestion failed, stop before fit card
    if not outfit or outfit.strip() == "":
        session["error"] = (
            "The outfit suggestion tool returned nothing, so I could not "
            "create a fit card. Try again or add more wardrobe details."
        )
        return session

    # Step 8: Call create_fit_card with outfit and selected item from state
    fit_card = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30 size M",
        wardrobe=get_example_wardrobe(),
    )

    print("Parsed:", session["parsed"])
    print("Retry note:", session["retry_note"])

    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )

    print("Parsed:", session2["parsed"])
    print(f"Selected item: {session2['selected_item']}")
    print(f"Outfit suggestion: {session2['outfit_suggestion']}")
    print(f"Fit card: {session2['fit_card']}")
    print(f"Error message: {session2['error']}")

    print("\n\n=== Empty wardrobe path ===\n")
    session3 = run_agent(
        query="looking for a vintage graphic tee under $50",
        wardrobe=get_empty_wardrobe(),
    )

    print("Parsed:", session3["parsed"])
    print("Retry note:", session3["retry_note"])

    if session3["error"]:
        print(f"Error: {session3['error']}")
    else:
        print(f"Found: {session3['selected_item']['title']}")
        print(f"\nOutfit: {session3['outfit_suggestion']}")
        print(f"\nFit card: {session3['fit_card']}")