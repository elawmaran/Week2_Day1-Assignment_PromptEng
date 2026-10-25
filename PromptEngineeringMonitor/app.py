
from pathlib import Path
from datetime import datetime
import json
import re

import ollama
import streamlit as st

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
PROMPT_FILE = BASE_DIR / "meal_plan_prompt.md"
REPORTS_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Prompt Engineering Monitor",
    page_icon="🧪",
    layout="wide",
)

st.title("Prompt Engineering Monitor")
st.caption("Test, evaluate, compare, and save reusable prompts with a local AI model.")

DEFAULT_PROMPT = """# ROLE
You are a practical meal-planning assistant specialising in balanced South Indian vegetarian meals. Give general educational suggestions, not medical diagnosis or treatment.

# FOR — EDITABLE USER DETAILS
Age: {age}
Location: Chennai, Tamil Nadu, India
Diet: Vegetarian; dairy allowed; no eggs
Activity level: {activity}
Goal: {goal}
Allergies: {allergies}
Disliked foods: {dislikes}
Household size: 1 adult
Maximum cooking time per meal: {cooking_time} minutes
Ingredient preference: Affordable, locally available South Indian ingredients
Medical considerations: {medical}

# CONSTRAINTS
- Plan Monday through Sunday.
- Include exactly four meals daily: breakfast, lunch, snack, and dinner.
- Use familiar South Indian vegetarian dishes and practical ingredients.
- Include a specific dish name, portion size, and brief preparation note for every meal.
- Include sensible variety in protein sources, vegetables, fibre-rich foods, and carbohydrates.
- Respect allergies, dislikes, dietary restrictions, and cooking-time limits.
- Do not promise medical outcomes or recommend extreme dietary restrictions.

# OUTPUT FORMAT
Return one Markdown table with these columns:
| Day | Meal | Dish | Portion | Preparation note |

Provide exactly 28 data rows: seven days multiplied by four meals.
Every day must contain breakfast, lunch, snack, and dinner exactly once.
After the table, add a short section titled Planning Notes.

# AVOID
Meat, fish, seafood, eggs, specified allergens, and disliked foods.
Avoid vague dish names, expensive specialty ingredients, and unsupported medical claims.

# FINAL QUALITY CHECK
Verify all seven days, 28 meal rows, four meals per day, portions, preparation notes, and user restrictions before answering.
"""


def build_prompt(values):
    return DEFAULT_PROMPT.format(**values)


def evaluate_plan(answer, values):
    """Basic structural checks; human review is still necessary."""
    lines = answer.splitlines()
    table_rows = [
        line for line in lines
        if line.strip().startswith("|")
        and "---" not in line
        and "Day" not in line
    ]

    day_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ]
    meal_names = ["breakfast", "lunch", "snack", "dinner"]

    day_hits = {
        day: len(re.findall(rf"\b{day}\b", answer, re.IGNORECASE))
        for day in day_names
    }

    meal_hits = {
        meal: len(re.findall(rf"\b{meal}\b", answer, re.IGNORECASE))
        for meal in meal_names
    }

    checks = {
        "Contains a Markdown meal table": len(table_rows) >= 28,
        "All seven days are mentioned": all(day_hits.values()),
        "Contains all four meal labels": all(meal_hits.values()),
        "Contains portion-related wording": bool(
            re.search(r"\b(cup|cups|grams|g|pieces|medium|tbsp|tsp)\b",
                      answer, re.IGNORECASE)
        ),
        "Contains planning notes": "planning notes" in answer.lower(),
    }

    if values["allergies"].strip().lower() not in ("", "none", "none specified"):
        checks["Allergy instructions require manual review"] = False

    return checks


with st.sidebar:
    st.header("Run settings")
    model_name = st.text_input("Ollama model", value="qwen2.5:3b")
    run_label = st.text_input("Run label", value="Run 1")

    st.subheader("Editable FOR block")
    age = st.number_input("Age", min_value=18, max_value=100, value=38)
    activity = st.selectbox(
        "Activity level",
        ["Sedentary", "Lightly active", "Moderately active", "Very active"],
        index=2,
    )
    goal = st.selectbox(
        "Meal-planning goal",
        [
            "Improve meal quality",
            "Support healthy blood-sugar management",
            "Support gradual weight management",
        ],
    )
    allergies = st.text_input("Allergies", value="None specified")
    dislikes = st.text_input("Disliked foods", value="None specified")
    cooking_time = st.selectbox("Cooking time per meal", [15, 20, 30, 45, 60], index=2)
    medical = st.text_input(
        "Relevant considerations",
        value="Insulin resistance and prediabetes; no medical outcome guarantees",
    )

    st.caption("Change these details to compare the same prompt with different inputs.")

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
    ["Run prompt", "Compare runs", "Assignment files"]
)

with tab_run:
    st.subheader("Reusable prompt")
    st.text_area("Prompt preview", value=prompt, height=300, disabled=True)

    if st.button("Save reusable prompt", type="secondary"):
        PROMPT_FILE.write_text(prompt, encoding="utf-8")
        st.success(f"Saved prompt to {PROMPT_FILE.name}")

    if st.button("Run prompt with Ollama", type="primary"):
        with st.spinner(f"Generating a meal plan with {model_name}..."):
            try:
                response = ollama.chat(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Follow the user's prompt carefully. "
                                "Return the requested Markdown format."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    options={"temperature": 0.2},
                )
                answer = response["message"]["content"]

                checks = evaluate_plan(answer, values)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", run_label).strip("_")
                safe_label = safe_label or "Run"
                report_id = f"{timestamp}_{safe_label}"

                report = {
                    "report_id": report_id,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "label": run_label,
                    "model": model_name,
                    "user_inputs": values,
                    "prompt": prompt,
                    "answer": answer,
                    "checks": checks,
                }

                md_path = REPORTS_DIR / f"{report_id}.md"
                json_path = REPORTS_DIR / f"{report_id}.json"

                md_path.write_text(
                    f"# {run_label}\n\n"
                    f"**Model:** {model_name}\n\n"
                    f"**Timestamp:** {report['timestamp']}\n\n"
                    f"## Prompt\n\n{prompt}\n\n"
                    f"## Generated Meal Plan\n\n{answer}\n\n"
                    f"## Structural Checks\n\n"
                    + "\n".join(
                        f"- [{'x' if passed else ' '}] {name}"
                        for name, passed in checks.items()
                    ),
                    encoding="utf-8",
                )
                json_path.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                st.session_state["latest_report"] = report
                st.session_state["latest_md"] = md_path
                st.session_state["latest_json"] = json_path
                st.success("Generation complete. Markdown and JSON reports saved.")

            except Exception as exc:
                st.error(f"Could not run the model: {exc}")
                st.info(
                    "Check that Ollama is running and that the model name "
                    "matches the output of `ollama list`."
                )

    if "latest_report" in st.session_state:
        report = st.session_state["latest_report"]
        st.subheader("Generated result")
        st.caption(f"Run: {report['label']} | Model: {report['model']}")
        st.markdown(report["answer"])

        st.subheader("Structural checks")
        for name, passed in report["checks"].items():
            st.write(f"{'✅' if passed else '⚠️'} {name}")

        st.download_button(
            "Download Markdown report",
            data=st.session_state["latest_md"].read_text(encoding="utf-8"),
            file_name=st.session_state["latest_md"].name,
            mime="text/markdown",
        )
        st.download_button(
            "Download JSON report",
            data=st.session_state["latest_json"].read_text(encoding="utf-8"),
            file_name=st.session_state["latest_json"].name,
            mime="application/json",
        )

with tab_compare:
    st.subheader("Compare saved runs")
    json_files = sorted(REPORTS_DIR.glob("*.json"), reverse=True)

    if len(json_files) < 2:
        st.info("Run the prompt twice to compare two reports.")
    else:
        file_names = [path.name for path in json_files]
        left_name = st.selectbox("First run", file_names, index=0)
        right_name = st.selectbox("Second run", file_names, index=1)

        if left_name == right_name:
            st.warning("Choose two different reports.")
        else:
            left = json.loads(
                (REPORTS_DIR / left_name).read_text(encoding="utf-8")
            )
            right = json.loads(
                (REPORTS_DIR / right_name).read_text(encoding="utf-8")
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"### {left['label']}")
                st.write("Inputs")
                st.json(left["user_inputs"])
                st.markdown("Generated plan")
                st.markdown(left["answer"])
            with col2:
                st.markdown(f"### {right['label']}")
                st.write("Inputs")
                st.json(right["user_inputs"])
                st.markdown("Generated plan")
                st.markdown(right["answer"])

with tab_files:
    st.subheader("Assignment files")
    st.write("Expected project structure:")
    st.code(
        "promptEngineeringMonitor/\n"
        "├── app.py\n"
        "├── meal_plan_prompt.md\n"
        "├── requirements.txt\n"
        "├── venv/\n"
        "└── reports/\n"
        "    ├── first_run.md\n"
        "    ├── first_run.json\n"
        "    ├── second_run.md\n"
        "    └── second_run.json",
        language="text",
    )

    st.write("Use the Run prompt tab to save your reusable prompt and generate reports.")
    st.write(
        "Review the generated meal plan yourself. Automated checks are only "
        "basic structural checks and do not validate nutrition or medical safety."
    )
