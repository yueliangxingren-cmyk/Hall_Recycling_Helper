# Hall_Recycling_Helper
The app is for HKU residents checking a published rule for recycling an everyday item.

## Install and run

Requires Python 3.10+. From this folder:

```bash
py -m venv .venv              # Windows; on macOS/Linux use: python3 -m venv .venv
.venv\Scripts\activate        # Windows; on macOS/Linux use: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Then open http://127.0.0.1:8000 in a browser.

Rules live in `rules.json`. Restart the server after editing it.
