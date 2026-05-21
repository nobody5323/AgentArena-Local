from __future__ import annotations

from dataclasses import asdict, dataclass


TEST_KEYWORDS = ("test", "pytest", "unit test", "integration test", "测试")
RISK_KEYWORDS = ("risk", "注意", "caution", "edge case", "rollback", "风险")


@dataclass(frozen=True)
class PlanningScore:
    score: int
    keyword_hits: list[str]
    keyword_hit_rate: float
    has_test_plan: bool
    has_risks: bool
    modified_code: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def score_plan(
    *,
    plan_text: str,
    expected_keywords: list[str],
    modified_code: bool,
) -> PlanningScore:
    lowered = plan_text.lower()
    hits = [
        keyword
        for keyword in expected_keywords
        if keyword.lower() in lowered
    ]
    hit_rate = len(hits) / len(expected_keywords) if expected_keywords else 1.0
    no_code_points = 0 if modified_code else 30
    keyword_points = round(hit_rate * 40)
    has_test_plan = any(keyword in lowered for keyword in TEST_KEYWORDS)
    has_risks = any(keyword in lowered for keyword in RISK_KEYWORDS)
    score = no_code_points + keyword_points + (15 if has_test_plan else 0) + (15 if has_risks else 0)
    return PlanningScore(
        score=max(0, min(100, score)),
        keyword_hits=hits,
        keyword_hit_rate=hit_rate,
        has_test_plan=has_test_plan,
        has_risks=has_risks,
        modified_code=modified_code,
    )
