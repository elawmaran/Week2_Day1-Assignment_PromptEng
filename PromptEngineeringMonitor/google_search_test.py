
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --------------------------------------------------
# Project paths
# --------------------------------------------------

BASE_DIR = Path(__file__).parent
PROFILE_DIR = BASE_DIR / "gemini_browser_profile"
PROMPT_FILE = BASE_DIR / "meal_plan_prompt.md"
OUTPUT_FILE = BASE_DIR / "google_ai_response.md"

AI_MODE_URL = "https://www.google.com/ai"


def get_prompt():
    """Load the reusable prompt from the project folder."""
    if not PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Prompt file not found: {PROMPT_FILE}\n"
            "Create meal_plan_prompt.md first."
        )

    prompt = PROMPT_FILE.read_text(encoding="utf-8").strip()

    if not prompt:
        raise ValueError("meal_plan_prompt.md is empty.")

    return prompt


def open_google_ai_mode(page):
    """Open Google AI Mode."""
    page.goto(
        AI_MODE_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    print("Google AI Mode opened.")
    print("Waiting for the input box...")

    page.wait_for_timeout(2000)


def find_prompt_editor(page):
    """Find a visible prompt input."""
    selectors = [
        'textarea',
        '[contenteditable="true"]',
        '[role="textbox"]',
    ]

    for selector in selectors:
        locator = page.locator(selector).filter(visible=True)

        if locator.count() > 0:
            for index in range(locator.count()):
                candidate = locator.nth(index)

                try:
                    if candidate.is_visible() and candidate.is_enabled():
                        return candidate
                except Exception:
                    continue

    raise RuntimeError(
        "Could not find the Google AI Mode input box. "
        "Inspect the page and update the input selector."
    )


def submit_prompt(page, editor, prompt):
    """Enter and submit the prompt."""
    editor.fill(prompt)

    print("Prompt entered into Google AI Mode.")

    # Give the user a chance to verify the input before submission.
    input("Check the browser. Press Enter here to submit the prompt... ")

    # Try common accessible button names first.
    button_names = [
        "Send",
        "Submit",
        "Search",
        "Ask",
    ]

    for name in button_names:
        try:
            button = page.get_by_role(
                "button",
                name=name,
                exact=False,
            ).filter(visible=True)

            for index in range(button.count()):
                candidate = button.nth(index)

                if candidate.is_visible() and candidate.is_enabled():
                    candidate.click(timeout=3000)
                    print(f"Submitted using the '{name}' button.")
                    return
        except Exception:
            continue

    # Fallback: inspect common Google AI Mode send-button attributes.
    fallback_selectors = [
        'button[aria-label*="Send" i]',
        'button[aria-label*="Submit" i]',
        'button[aria-label*="Search" i]',
        'button[aria-label*="Ask" i]',
        'button[type="submit"]',
    ]

    for selector in fallback_selectors:
        try:
            buttons = page.locator(selector).filter(visible=True)

            for index in range(buttons.count()):
                candidate = buttons.nth(index)

                if candidate.is_visible() and candidate.is_enabled():
                    candidate.click(timeout=3000)
                    print("Submitted using a fallback button selector.")
                    return
        except Exception:
            continue

    # Last resort: use Enter in the prompt editor.
    print("No matching send button found. Trying Enter.")
    editor.press("Enter")


def wait_for_response(page):
    """Allow time for Google AI Mode to generate its response."""
    print("\nWaiting for the AI response.")
    print("Generation time depends on Google's response.")

    input(
        "When the complete answer is visible in the browser, "
        "press Enter here to capture the page text... "
    )

    # Wait briefly for the page to settle after user confirmation.
    page.wait_for_timeout(1000)


def save_response(page):
    """Save captured page text to a Markdown file."""
    page_text = page.locator("body").inner_text()

    if not page_text.strip():
        raise RuntimeError("The browser page returned no visible text.")

    captured_at = __import__("datetime").datetime.now().isoformat(
        timespec="seconds"
    )

    content = (
        "# Google AI Mode Response\n\n"
        f"- Source URL: {page.url}\n"
        f"- Captured at: {captured_at}\n\n"
        "## Captured Page Text\n\n"
        f"{page_text}\n"
    )

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("\nResponse text saved successfully.")
    print(f"File: {OUTPUT_FILE}")


def main():
    prompt = get_prompt()

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
        )

        try:
            page = (
                context.pages[0]
                if context.pages
                else context.new_page()
            )

            open_google_ai_mode(page)

            editor = find_prompt_editor(page)

            submit_prompt(page, editor, prompt)

            print(
                "\nIf the prompt was not submitted, "
                "inspect the browser and submit it manually."
            )

            wait_for_response(page)

            save_response(page)

            print("\nNext step: open google_ai_response.md in VS Code.")

        except PlaywrightTimeoutError as error:
            print(f"\nBrowser timeout: {error}")
            print(
                "Check that Google AI Mode loaded and the input is visible."
            )

        except Exception as error:
            print(f"\nError: {error}")

        finally:
            input("\nPress Enter to close the browser... ")
            context.close()


if __name__ == "__main__":
    main()
