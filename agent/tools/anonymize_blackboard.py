"""Make an anonymized test copy of Blackboard answers saved by `sla-agent fetch`.

Usage: python -m agent.tools.anonymize_blackboard SAVED_JSON OUTPUT_JSON
Keeps the structure, IDs of courses/items, course IDs and names, dates and content types.
Replaces the student's user record and ID, announcement titles and bodies, grades, feedback,
item titles and descriptions."""

import json
import re
import sys
from pathlib import Path

TEXT_KEYS = {"body": "Anonymized text.", "description": "Anonymized description.",
             "feedback": "<p>Anonymized feedback.</p>", "text": "8"}


def anonymize(raw):
    me = next((v.get("id") for k, v in raw.items() if k.startswith("/v1/users/me") and isinstance(v, dict)), None)
    counter = {"title": 0}

    def fake_title():
        counter["title"] += 1
        return f"Item {counter['title']}"

    def clean(value, key=None, parent_key=None):
        if isinstance(value, dict):
            return {k: clean(v, k, key) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v, key, parent_key) for v in value]
        if not isinstance(value, str):
            if key == "score" and isinstance(value, (int, float)) and parent_key != "score":
                return 8.0
            return value
        if me and me in value:
            value = value.replace(me, "_1_1")
        if key in TEXT_KEYS:
            return TEXT_KEYS[key]
        if key == "title":
            return fake_title()
        return value

    result = {}
    for path, body in raw.items():
        if path.startswith("/v1/users/me"):
            result["/v1/users/me"] = {"id": "_1_1"}
            continue
        result[path.replace(me, "_1_1") if me else path] = clean(body)
    return result, me


if __name__ == "__main__":
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    raw = json.loads(source.read_text(encoding="utf-8"))
    result, me = anonymize(raw)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    text = json.dumps(result, ensure_ascii=False)
    user = raw.get("/v1/users/me", {})
    personal = [v for v in (me, user.get("userName"), user.get("studentId"),
                            (user.get("contact") or {}).get("email"),
                            (user.get("name") or {}).get("given"), (user.get("name") or {}).get("family")) if v]
    leaks = sum(v in text for v in personal)
    emails = len(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text))
    print(f"answers: {len(result)}, personal values still present: {leaks}, emails: {emails}")
