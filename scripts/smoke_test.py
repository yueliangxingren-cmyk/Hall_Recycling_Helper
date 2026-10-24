"""One real HTTP /ask test. Live mode refuses to pass on provider fallback.

Start uvicorn first, then run `python scripts/smoke_test.py`.
Use --offline for the same rule via exact lookup, without provider requirements.
Use --exact to require a live chat response with exact lookup, without embeddings.
Use --in-process to call the real FastAPI route without starting a TCP server.
"""

import argparse
import json
import math
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen


def request_answer(item, base_url, in_process=False, offline=False):
    payload = {"item": item, "context": "hku_hall"}
    if in_process:
        # Direct script execution puts scripts/, rather than the project root,
        # on sys.path. Import the same application uvicorn serves.
        root = str(Path(__file__).resolve().parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from fastapi.testclient import TestClient

        from app import create_app
        from providers import ModelProvider, Settings

        settings = Settings() if offline else Settings.from_env()
        with TestClient(create_app(ModelProvider(settings))) as client:
            response = client.post("/ask", json=payload)
        if response.status_code != 200:
            raise ValueError("The application did not return HTTP 200")
        return response.json()

    request = Request(
        base_url.rstrip("/") + "/ask",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--in-process", action="store_true",
                        help="Use the actual FastAPI route without a TCP listener (requires dev dependencies)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--exact", action="store_true")
    args = parser.parse_args()
    exact = args.offline or args.exact
    item = "plastic bottle" if exact else "plastic beverage bottle"
    try:
        result = request_answer(item, args.base_url, args.in_process, args.offline)
        if not isinstance(result, dict):
            raise ValueError("Expected an object response")
    except ImportError:
        print("FAIL: install requirements-dev.txt for the in-process test.")
        return 1
    except (URLError, OSError, ValueError):
        print("FAIL: /ask could not be reached or returned a valid response.")
        if not args.in_process:
            print("Start uvicorn first, or use --in-process.")
        return 1

    rules_path = Path(__file__).resolve().parent.parent / "rules.json"
    with rules_path.open(encoding="utf-8") as file:
        expected = next(rule for rule in json.load(file) if rule["item"] == "plastic bottle")
    checks = {
        "published item": result.get("matched_item") == expected["item"],
        "status": result.get("status") == "ok",
        "bin including location exception": result.get("bin") == expected["hku_hall_bin"],
        "all preparation steps": result.get("prep_step") == expected["prep_step"],
        "HKU citation": result.get("source_url") == expected["hku_source_url"],
        "verification date": result.get("date_checked") == expected["date_checked"],
        "retrieval": result.get("retrieval_method") == ("exact" if exact else "embedding"),
    }
    if not exact:
        score = result.get("similarity")
        checks["cosine > 0.85"] = type(score) in (int, float) and math.isfinite(score) and score > 0.85
    if not args.offline:
        checks["validated live LLM"] = result.get("grounding") == "llm"
    for name, passed in checks.items():
        print(f'{"PASS" if passed else "FAIL"}: {name}')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
