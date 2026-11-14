"""A15: AI answers for the Check view that do not depend on the network on stage.

Each question goes to each model in answers.yaml through the Gemini endpoint at temperature 0. A model the key
cannot use is skipped and reported. Output: data/answers.json (question, model, date, answer).
"""

import json
import re
from datetime import UTC, datetime

import yaml

from engine import gemini
from pipeline.fetch import DATA, ROOT

SYSTEM = "Answer the question in English in 3 to 5 factual sentences."


def ask(model: str, question: str) -> str:
    r = gemini.client().chat.completions.create(
        model=model,
        temperature=0,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
    )
    text = r.choices[0].message.content or ""
    text = re.sub(r"<thought>.*?(</thought>|$)", "", text, flags=re.S)  # Gemma prints its reasoning first
    return text.strip()


def main() -> None:
    spec = yaml.safe_load((ROOT / "pipeline" / "answers.yaml").read_text(encoding="utf-8"))
    out, skipped = [], {}
    today = datetime.now(UTC).date().isoformat()
    for model in spec["models"]:
        for q in spec["questions"]:
            gemini._BUCKET.take()
            try:
                a = ask(model, q)
            except Exception as e:  # noqa: BLE001
                skipped[model] = f"{type(e).__name__} {getattr(e, 'status_code', '')}".strip()
                break
            out.append({"question": q, "model": model, "date": today, "answer": a})
            print(f"{model}: {q} -> {a[:90]}")
    (DATA / "answers.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"stored {len(out)} answers in data/answers.json; skipped models: {skipped or 'none'}")


if __name__ == "__main__":
    main()
