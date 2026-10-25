
from pathlib import Path
from datetime import datetime
import json
import re

import streamlit as st

# --------------------------------------------------
# Project configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
PROMPT_FILE = BASE_DIR / "meal_plan_prompt.md"

REPORTS_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Prompt Engineering Monitor",
    page_icon="🧪",
    layout="wide",
)

# --------------------------------------------------
# Reusable prompt template
# --------------------------------------------------

PROMPT_TEMPLATE = """# Reusable Prompt: 7-Day Healthy South Indian Vegetarian Meal Plan

## ROLE
You are a practical meal-planning assistant specialising in balanced South Indian vegetarian meals. Provide general educational suggestions, not medical diagnosis or treatment.

## FOR — EDITABLE USER DETAILS
- Age: {age}
- Location: Chennai, Tamil Nadu, India
- Diet: Vegetarian; dairy allowed; no eggs
- Activity level: {activity}
- Goal: {goal}
- Allergies: {allergies}
- Disliked foods: {dislikes}
- Household size: 1 adult
- Maximum cooking time per meal: {cooking_time} minutes
- Ingredient preference: Affordable, locally available South Indian ingredients
- Medical considerations: {medical}

## CONSTRAINTS
- Plan Monday through Sunday.
- Include exactly four meals daily: breakfast, lunch, snack, and dinner.
- Use familiar South Indian vegetarian dishes and practical ingredients.
- Include a named dish, portion size, and brief preparation note for every meal.
- Include variety in protein sources, vegetables, fibre-rich foods, and carbohydrates.
- Respect all allergies, dislikes, dietary restrictions, and cooking-time limits.
- Do not promise medical outcomes or recommend extreme dietary restrictions.

## OUTPUT FORMAT
Return one Markdown table with exactly these columns:
| Day | Meal | Dish | Portion | Preparation note |

Provide exactly 28 data rows: seven days multiplied by four meals.
Each day must have breakfast, lunch, snack, and dinner exactly once.
After the table, add a section titled Planning Notes.

## AVOID
Meat, fish, seafood, eggs, specified allergens, and disliked foods.
Avoid vague dish names, expensive specialty ingredients, and unsupported medical claims.

## FINAL QUALITY CHECK
Verify all seven days, 28 meal rows, four meals per day, portions, preparation notes, and user restrictions before answering.
"""


def build_prompt(values):
    return PROMPT_TEMPLATE.format(**values)


def analyse_response(answer, values):
    """Run basic structural checks on the pasted AI response."""
    lines = answer.splitlines()

    table_lines = [
        line.strip()
        for line in lines
        if line.strip().startswith("|")
        and not re.search(r"^\|[\s:|-]+\|$", line.strip())
    ]

    data_rows = [
        line for line in table_lines
        if not re.search(r"\bDay\s*\|", line, re.IGNORECASE)
    ]

    day_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ]
    meal_names = ["breakfast", "lunch", "snack", "dinner"]

    day_counts = {day: 0 for day in day_names}
    meal_counts = {meal: 0 for meal in meal_names}
    valid_rows = []

    for line in data_rows:
        cells = [cell.strip() for cell in line.strip("|").split("|")]

        if len(cells) < 5:
            continue

        day = cells[0].strip().title()
        meal = cells[1].strip().lower()

        if day in day_counts and meal in meal_counts:
            day_counts[day] += 1
            meal_counts[meal] += 1
            valid_rows.append((day, meal, cells))

    checks = {
        "All seven days included": all(day_counts.values()),
        "Exactly 28 valid meal rows": len(valid_rows) == 28,
        "Each day has exactly four meals": all(
            day_counts[day] == 4 for day in day_names
        ),
        "All four meal types are present": all(
            meal_counts[meal] > 0 for meal in meal_names
        ),
        "Portion sizes appear in the table": any(
            cells[3] and len(cells[3]) > 1 for _, _, cells in valid_rows
        ),
        "Preparation notes appear in the table": all(
            cells[4] for _, _, cells in valid_rows
        ) if valid_rows else False,
        "Planning Notes section present": "planning notes" in answer.lower(),
    }

    if values["allergies"].strip().lower() not in (
        "", "none", "none specified"
    ):
        checks["Allergy compliance needs manual review"] = False

    if values["dislikes"].strip().lower() not in (
        "", "none", "none specified"
    ):
        checks["Dislike compliance needs manual review"] = False

    return checks, day_counts, meal_counts, len(valid_rows)


def save_report(label, source, prompt, answer, values, checks):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_")
    safe_label = safe_label or "Run"
    report_id = f"{timestamp}_{safe_label}"

    report = {
        "report_id": report_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "source": source,
        "user_inputs": values,
        "prompt": prompt,
        "answer": answer,
        "checks": checks,
    }

    md_path = REPORTS_DIR / f"{report_id}.md"
    json_path = REPORTS_DIR / f"{report_id}.json"

    check_text = "\n".join(
        f"- [{'x' if passed else ' '}] {name}"
        for name, passed in checks.items()
    )

    markdown = (
        f"# {label}\n\n"
        f"- Source: {source}\n"
        f"- Timestamp: {report['timestamp']}\n\n"
        f"## User Inputs\n\n```json\n"
        f"{json.dumps(values, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Prompt\n\n{prompt}\n\n"
        f"## Generated Response\n\n{answer}\n\n"
        f"## Structural Checks\n\n{check_text}\n"
    )

    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return report, md_path, json_path


# --------------------------------------------------
# Header and sidebar
# --------------------------------------------------

st.title("Prompt Engineering Monitor")
st.caption(
    "Prepare prompts, evaluate AI responses, compare runs, "
    "and export reports — using Google AI Mode."
)

with st.sidebar:
    st.header("Run settings")
    st.caption(
        "Change the details below, then click Update Prompt to apply them."
    )

    with st.form("run_settings_form"):
        run_label = st.text_input("Run label", value="Run 1")

        st.subheader("Editable FOR block")

        age = st.number_input(
            "Age", min_value=18, max_value=100, value=38
        )

        activity = st.selectbox(
            "Activity level",
            [
                "Sedentary",
                "Lightly active",
                "Moderately active",
                "Very active",
            ],
            index=2,
        )

        goal = st.selectbox(
            "Meal-planning goal",
            [
                "Improve meal quality",
                "Support healthy blood-sugar management",
                "Support gradual weight management",
            ],
            index=1,
        )

        allergies = st.text_input(
            "Allergies", value="None specified"
        )

        dislikes = st.text_input(
            "Disliked foods", value="None specified"
        )

        cooking_time = st.selectbox(
            "Cooking time per meal (minutes)",
            [15, 20, 30, 45, 60],
            index=2,
        )

        medical = st.text_input(
            "Relevant considerations",
            value=(
                "Insulin resistance and prediabetes; "
                "no medical outcome guarantees"
            ),
        )

        update_prompt = st.form_submit_button(
            "Update Prompt",
            type="primary",
            width="stretch",
        )

    if update_prompt:
        st.session_state["prompt_updated_notice"] = True
    else:
        st.session_state["prompt_updated_notice"] = False

values = {
    "age": age,
    "activity": activity,
    "goal": goal,
    "allergies": allergies,
    "dislikes": dislikes,
    "cooking_time": cooking_time,
    "medical": medical,
}

prompt = build_prompt(values)

tab_run, tab_compare, tab_files = st.tabs(
    ["Prepare & Analyse", "Compare Runs", "Assignment Files"]
)

# --------------------------------------------------
# Tab 1: Prepare prompt and analyse response
# --------------------------------------------------

with tab_run:
    st.subheader("1. Prepare your reusable prompt")

    st.markdown(
        "Copy the prompt below, open Google AI Mode, submit it "
        "manually, and copy the completed answer back here."
    )

    # Refresh this read-only-by-convention preview from the committed settings.
    # Setting the session value before rendering ensures the preview reflects
    # the latest values after Update Prompt is pressed.
    st.session_state["prompt_preview"] = prompt

    st.text_area(
        "Prompt to send to Google AI Mode",
        height=320,
        key="prompt_preview",
    )

    if st.session_state.get("prompt_updated_notice", False):
        st.success("Prompt updated. Review it below before sending it to Google AI Mode.")

    col1, col2 = st.columns(2)

    with col1:
        st.link_button(
            "Open Google AI Mode",
            "https://www.google.com/ai",
            width="stretch",
        )

    with col2:
        if st.button(
            "Save reusable prompt",
            width="stretch",
        ):
            PROMPT_FILE.write_text(prompt, encoding="utf-8")
            st.success("Saved meal_plan_prompt.md")

    st.divider()
    st.subheader("2. Paste the AI-generated response")

    source = st.selectbox(
        "Response source",
        ["Google AI Mode", "Gemini website", "Other"],
    )

    response_text = st.text_area(
        "Paste the complete AI response here",
        value="",
        height=350,
        placeholder=(
            "Paste the generated Markdown meal plan here, "
            "including its table and Planning Notes."
        ),
        key="response_input",
    )

    if st.button(
        "Analyse and Save Run",
        type="primary",
        width="stretch",
    ):
        if not response_text.strip():
            st.warning("Paste an AI response before analysing.")
        else:
            checks, day_counts, meal_counts, row_count = (
                analyse_response(response_text, values)
            )

            report, md_path, json_path = save_report(
                label=run_label,
                source=source,
                prompt=prompt,
                answer=response_text,
                values=values,
                checks=checks,
            )

            st.session_state["latest_report"] = report
            st.session_state["latest_md_path"] = str(md_path)
            st.session_state["latest_json_path"] = str(json_path)

            st.success(
                f"Run saved. Detected {row_count} valid meal rows."
            )

    if "latest_report" in st.session_state:
        report = st.session_state["latest_report"]

        st.divider()
        st.subheader(f"3. Analysis: {report['label']}")

        passed = sum(
            1 for value in report["checks"].values() if value
        )
        total = len(report["checks"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Checks passed", f"{passed}/{total}")
        c2.metric("Response source", report["source"])
        c3.metric("Saved run", report["label"])

        st.markdown("#### Validation checklist")

        for name, passed_check in report["checks"].items():
            st.write(
                f"{'✅' if passed_check else '⚠️'} {name}"
            )

        st.markdown("#### Generated response")
        st.markdown(report["answer"])

        md_path = Path(st.session_state["latest_md_path"])
        json_path = Path(st.session_state["latest_json_path"])

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                "Download Markdown report",
                data=md_path.read_text(encoding="utf-8"),
                file_name=md_path.name,
                mime="text/markdown",
                width="stretch",
            )

        with d2:
            st.download_button(
                "Download JSON report",
                data=json_path.read_text(encoding="utf-8"),
                file_name=json_path.name,
                mime="application/json",
                width="stretch",
            )

        st.caption(
            "Automated checks validate structure only. "
            "They do not establish nutritional or medical safety."
        )

# --------------------------------------------------
# Tab 2: Compare saved runs
# --------------------------------------------------

with tab_compare:
    st.subheader("Compare two saved AI responses")

    json_files = sorted(
        REPORTS_DIR.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if len(json_files) < 2:
        st.info(
            "Save at least two runs with different labels or inputs "
            "to compare them here."
        )
    else:
        file_names = [path.name for path in json_files]

        left_name = st.selectbox(
            "First run",
            file_names,
            index=0,
            key="compare_left",
        )

        right_default = 1 if len(file_names) > 1 else 0

        right_name = st.selectbox(
            "Second run",
            file_names,
            index=right_default,
            key="compare_right",
        )

        if left_name == right_name:
            st.warning("Select two different report files.")
        else:
            left = json.loads(
                (REPORTS_DIR / left_name).read_text(
                    encoding="utf-8"
                )
            )
            right = json.loads(
                (REPORTS_DIR / right_name).read_text(
                    encoding="utf-8"
                )
            )

            left_col, right_col = st.columns(2)

            with left_col:
                st.markdown(f"### {left['label']}")
                st.caption(left["source"])
                st.json(left["user_inputs"])

                left_passed = sum(
                    1 for value in left["checks"].values() if value
                )
                st.metric(
                    "Checks passed",
                    f"{left_passed}/{len(left['checks'])}",
                )

                st.markdown(left["answer"])

            with right_col:
                st.markdown(f"### {right['label']}")
                st.caption(right["source"])
                st.json(right["user_inputs"])

                right_passed = sum(
                    1 for value in right["checks"].values() if value
                )
                st.metric(
                    "Checks passed",
                    f"{right_passed}/{len(right['checks'])}",
                )

                st.markdown(right["answer"])

            st.divider()
            st.subheader("Validation comparison")

            comparison = []

            for check_name in dict.fromkeys(
                list(left["checks"]) + list(right["checks"])
            ):
                comparison.append({
                    "Validation": check_name,
                    left["label"]: (
                        "Pass" if left["checks"].get(check_name, False)
                        else "Review"
                    ),
                    right["label"]: (
                        "Pass" if right["checks"].get(check_name, False)
                        else "Review"
                    ),
                })

            st.dataframe(
                comparison,
                width="stretch",
                hide_index=True,
            )

# --------------------------------------------------
# Tab 3: Assignment files
# --------------------------------------------------

with tab_files:
    st.subheader("Project files")

    st.code(
        "PromptEngineeringMonitor/\n"
        "├── app.py\n"
        "├── meal_plan_prompt.md\n"
        "├── requirements.txt\n"
        "├── google_search_test.py  # Optional browser test\n"
        "├── reports/\n"
        "│   ├── <run_id>.md\n"
        "│   └── <run_id>.json\n"
        "└── venv/",
        language="text",
    )

    st.markdown("### Saved reports")

    saved_reports = sorted(
        REPORTS_DIR.glob("*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not saved_reports:
        st.info("No reports saved yet.")
    else:
        for report_file in saved_reports:
            if report_file.is_file():
                st.write(f"📄 {report_file.name}")

    st.markdown("### Prompt improvements")

    st.text_area(
        "Write 2–3 lines about improvements between runs",
        key="prompt_improvements",
        placeholder=(
            "Example: I made the table structure explicit and required "
            "exactly 28 meal rows. I also clarified portion sizes and "
            "dietary restrictions to make the output easier to validate."
        ),
    )

    if st.button("Save prompt improvement notes"):
        notes = st.session_state.get("prompt_improvements", "").strip()

        if notes:
            notes_path = REPORTS_DIR / "prompt_improvements.md"
            notes_path.write_text(
                "# Prompt Improvement Notes\n\n" + notes + "\n",
                encoding="utf-8",
            )
            st.success("Improvement notes saved.")
        else:
            st.warning("Enter your notes first.")
