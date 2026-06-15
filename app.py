"""
app.py

Gradio interface for FitFindr. The layout and wiring are already set up.
This file calls run_agent() and maps the session results to the three output panels.

Run with:
    python app.py

Then open the localhost URL shown in your terminal.
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── query handler ─────────────────────────────────────────────────────────────

def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Args:
        user_query: The text the user typed into the search box.
        wardrobe_choice: Either "Example wardrobe" or "Empty wardrobe (new user)".

    Returns:
        A tuple of three strings:
            (listing_text, outfit_suggestion, fit_card)

        Each string maps to one of the three output panels in the UI.
    """

    # Step 1: Guard against empty query
    if not user_query or user_query.strip() == "":
        return (
            "Please enter a clothing item to search for, such as 'vintage graphic tee under $30'.",
            "",
            "",
        )

    # Step 2: Select wardrobe based on user choice
    if wardrobe_choice == "Empty wardrobe (new user)":
        wardrobe = get_empty_wardrobe()
    else:
        wardrobe = get_example_wardrobe()

    # Step 3: Call the FitFindr agent
    session = run_agent(
        query=user_query,
        wardrobe=wardrobe,
    )

    # Step 4: If the agent stopped early, show the error
    if session["error"]:
        error_text = f"""
Search stopped early.

Reason:
{session["error"]}

Parsed request:
- Description: {session["parsed"].get("description")}
- Size: {session["parsed"].get("size")}
- Max price: {session["parsed"].get("max_price")}

What to try next:
- Use a broader item description
- Increase your max price
- Remove the size filter
"""
        return error_text.strip(), "", ""

    # Step 5: Format the selected listing
    item = session["selected_item"]

    colors = item.get("colors", [])
    if isinstance(colors, list):
        colors_text = ", ".join(colors)
    else:
        colors_text = str(colors)

    style_tags = item.get("style_tags", [])
    if isinstance(style_tags, list):
        style_tags_text = ", ".join(style_tags)
    else:
        style_tags_text = str(style_tags)

    listing_text = f"""
Top listing found:

Title: {item.get("title")}
Price: ${item.get("price")}
Platform: {item.get("platform")}
Size: {item.get("size")}
Condition: {item.get("condition")}
Brand: {item.get("brand")}
Category: {item.get("category")}
Colors: {colors_text}
Style tags: {style_tags_text}

Description:
{item.get("description")}
"""

    # Step 6: Show retry note if fallback logic was used
    if session.get("retry_note"):
        listing_text = session["retry_note"] + "\n\n" + listing_text

    # Step 7: Return outputs to the three Gradio panels
    return (
        listing_text.strip(),
        session["outfit_suggestion"],
        session["fit_card"],
    )


# ── interface ─────────────────────────────────────────────────────────────────

EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "designer ballgown size XXS under $5",   # deliberate no-results test
]


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.

Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )

            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=8,
                interactive=False,
            )

            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=8,
                interactive=False,
            )

            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=8,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()