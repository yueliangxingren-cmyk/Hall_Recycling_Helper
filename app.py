"""Hall Recycling Helper: FastAPI backend.

Run with:  uvicorn app:app --reload
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from retrieval import find_rule

STATIC_DIR = Path(__file__).parent / "static"

NOT_COVERED_MESSAGE = "Not covered by published rules — please ask your hall office."
REFUSED_MESSAGE = (
    "This item may be hazardous and must not go in ordinary recycling bins. "
    "Please contact your hall staff or use a proper hazardous-waste collection point."
)

# Hazard gate: if any of these appears anywhere in the item text, we refuse
# before looking up rules. Substring matching is deliberate: it errs on the
# side of refusing (e.g. "paintbrush" is refused because it contains "paint").
# Batteries are NOT here: HKU's re Kiosk collects rechargeable batteries, so they are
# handled by a rule in rules.json (a cross-system test case in the proposal).
HAZARD_KEYWORDS = [
    "power bank",
    "lithium",
    "paint",
    "thinner",
    "solvent",
    "chemical",
    "fluorescent tube",
    "fluorescent lamp",
    "mercury",
    "pesticide",
    "bleach",
    "gas canister",
    "aerosol",
    "syringe",
    "needle",
]

app = FastAPI(title="Hall Recycling Helper")


class AskRequest(BaseModel):
    item: str
    context: Literal["hku_hall", "epd_smart"]


class AskResponse(BaseModel):
    status: Literal["ok", "not_covered", "refused"]
    bin: str = ""
    prep_step: str = ""
    source_url: str = ""
    date_checked: str = ""
    message: str = ""


def is_hazardous(item: str) -> bool:
    text = item.lower()
    return any(keyword in text for keyword in HAZARD_KEYWORDS)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    # 1. Hazard gate runs BEFORE retrieval.
    if is_hazardous(req.item):
        return AskResponse(status="refused", message=REFUSED_MESSAGE)

    # 2. Look up the published rule.
    rule = find_rule(req.item, req.context)
    if rule is None:
        return AskResponse(status="not_covered", message=NOT_COVERED_MESSAGE)

    return AskResponse(
        status="ok",
        bin=rule["bin"],
        prep_step=rule["prep_step"],
        source_url=rule["source_url"],
        date_checked=rule["date_checked"],
        message=f"Rule found for \"{rule['item']}\".",
    )
