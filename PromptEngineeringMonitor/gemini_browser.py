
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
PROFILE_DIR = BASE_DIR / "gemini_browser_profile"
PROMPT_FILE = BASE_DIR / "meal_plan_prompt.md"
OUTPUT_FILE = BASE_DIR / "gemini_response.md"


def run_gemini():
    if not PROMPT_FILE.exists():
        raise FileNotFoundError("meal_plan_prompt.md was not found.")

    prompt = PROMPT_FILE.read_text(encoding="utf-8")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
        )

        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(
                "https://gemini.google.com/",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            print("Waiting for Gemini to load...")
            page.wait_for_timeout(3000)

            # Find a visible, editable prompt input.
            editor = page.locator(
                'div[contenteditable="true"], '
                'textarea, '
                '[role="textbox"]'
            ).filter(visible=True).first

            editor.wait_for(state="visible", timeout=30000)
            editor.fill(prompt)

            print("Prompt entered. Submitting to Gemini...")

            # Locate the send button using common accessible labels.
            send_button = page.get_by_role(
                "button",
                name="Send",
                exact=False,
            )

            if send_button.count() > 0 and send_button.first.is_visible():
                send_button.first.click()
            else:
                # Fallback: use Enter only if the input is ready.
                editor.press("Enter")

            print("Waiting for Gemini to generate its response...")
            page.wait_for_timeout(5000)

            input(
                "When Gemini has finished generating, "
                "press Enter here to capture the response..."
            )

            # Capture visible conversation text for inspection.
            response_text = page.locator("body").inner_text()

            OUTPUT_FILE.write_text(
                "# Gemini Response\n\n"
                f"Source: Gemini website\n\n"
                f"Captured from: {page.url}\n\n"
                "## Captured page text\n\n"
                f"{response_text}\n",
                encoding="utf-8",
            )

            print(f"Saved captured page text to: {OUTPUT_FILE}")

        finally:
            context.close()


if __name__ == "__main__":
    run_gemini()
