"""Hall Recycling Helper: FastAPI backend.

Run with:  uvicorn app:app --reload
"""

from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from grounding import ground_answer
from providers import ModelProvider, Settings
from retrieval import RULES, RuleRetriever

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

def create_app(provider: ModelProvider | None = None, rules: list[dict] | None = None) -> FastAPI:
    application = FastAPI(title="Hall Recycling Helper")
    application.state.provider = provider or ModelProvider(Settings.from_env())
    application.state.retriever = RuleRetriever(
        RULES if rules is None else rules, application.state.provider,
    )

    @application.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @application.post("/ask", response_model=AskResponse)
    def ask(req: AskRequest) -> AskResponse:
        # The hazard gate must run before *any* model or retrieval call.
        if is_hazardous(req.item):
            return AskResponse(status="refused", message=REFUSED_MESSAGE)
        rule = application.state.retriever.find_rule(req.item, req.context)
        if rule is None:
            return AskResponse(status="not_covered", message=NOT_COVERED_MESSAGE)

        message, grounding = ground_answer(rule, application.state.provider)
        return AskResponse(
            status="ok", bin=rule["bin"], prep_step=rule["prep_step"],
            source_url=rule["source_url"], date_checked=rule["date_checked"],
            message=message, matched_item=rule["item"],
            retrieval_method=rule["retrieval_method"], similarity=rule["similarity"],
            grounding=grounding,
        )

    return application


class AskRequest(BaseModel):
    item: str = Field(min_length=1, max_length=500)
    context: Literal["hku_hall", "epd_smart"]

    @field_validator("item")
    @classmethod
    def trim_item(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Item cannot be blank")
        return value


class AskResponse(BaseModel):
    status: Literal["ok", "not_covered", "refused"]
    bin: str = ""
    prep_step: str = ""
    source_url: str = ""
    date_checked: str = ""
    message: str = ""
    matched_item: str = ""
    retrieval_method: Literal["exact", "embedding", "none"] = "none"
    similarity: float | None = None
    grounding: Literal["llm", "published_rule", "not_applicable"] = "not_applicable"


def is_hazardous(item: str) -> bool:
    text = " ".join(item.casefold().split())
    return any(keyword in text for keyword in HAZARD_KEYWORDS)


app = create_app()
