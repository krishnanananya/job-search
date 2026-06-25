import re

from config.profile import PROFILE

_SKILLS = set(PROFILE["skills"])

# Core role title patterns — strong signal this is in Ananya's primary target set
_CORE_PATTERNS = [
    (r"\bquant(itative)?\s+(research(er)?|analyst|trader|trading|strategist|developer|scientist)\b", 50),
    (r"\bquant(itative)?\b", 40),
    (r"\binvestment associate\b", 45),
    (r"\bportfolio (analyst|associate|manager|scientist)\b", 35),
    (r"\bsystematic (trader|researcher|strategist|analyst)\b", 45),
    (r"\balpha (research(er)?|generation|signal)\b", 45),
    (r"\bexecution (trader|analyst|researcher|strategist|scientist)\b", 40),
    (r"\b(fixed income|rates|credit|fx|macro|commodities)\s+(analyst|researcher|strategist|associate|quant)\b", 35),
    (r"\brisk (analyst|associate|manager|researcher|quant)\b", 30),
    (r"\bderivatives (analyst|trader|researcher|quant)\b", 35),
    (r"\btrading (analyst|researcher|associate|strategist|scientist)\b", 35),
    (r"\bsignal (researcher|research|developer|analyst)\b", 45),
    (r"\bstatistical (arbitrage|researcher|analyst)\b", 45),
    (r"\bmarket (making|microstructure) (researcher|analyst|scientist|developer)\b", 40),
    (r"\bportfolio management\b", 25),
    (r"\bfactor (research(er)?|analyst|model)\b", 40),
    (r"\bbacktest(ing)?\b", 25),
]

# Stretch role title patterns — adjacent / relevant given her background
_STRETCH_PATTERNS = [
    (r"\bdata scientist\b", 25),
    (r"\b(machine learning|ml) (engineer|scientist|researcher)\b", 22),
    (r"\bresearch (analyst|associate|scientist)\b", 20),
    (r"\bvc (associate|analyst|partner)\b", 20),
    (r"\bventure (capital|associate|analyst|partner)\b", 20),
    (r"\binvestment (analyst|banker|banking analyst)\b", 22),
    (r"\bfinancial (engineer|data scientist|analyst)\b", 22),
    (r"\banalytics engineer\b", 18),
    (r"\bsoftware engineer\b", 10),
    (r"\bdata engineer\b", 12),
    (r"\bapplied (scientist|researcher)\b", 20),
    (r"\beconomist\b", 25),
]

# Company categories that elevate a stretch title to "also interesting"
_QUANT_CATEGORIES = {"quant_fund", "trading_shop", "crypto_trading"}
_FINANCE_CATEGORIES = {"bank", "asset_manager"} | _QUANT_CATEGORIES


def _match(text: str, patterns: list[tuple]) -> tuple[int, str]:
    """Return (total_score, first_matched_label)."""
    total = 0
    label = ""
    text_lower = text.lower()
    for pattern, points in patterns:
        if re.search(pattern, text_lower):
            total += points
            if not label:
                label = re.search(pattern, text_lower).group(0)
    return total, label


def _skill_score(description: str) -> tuple[int, list[str]]:
    if not description:
        return 0, []
    desc_lower = description.lower()
    matched = [s for s in _SKILLS if re.search(r"\b" + re.escape(s) + r"\b", desc_lower)]
    return min(25, len(matched) * 3), matched


def score_job(job: dict) -> dict:
    title = job.get("title", "")
    description = job.get("description", "")
    category = job.get("company_category", "")

    core_score, core_label = _match(title, _CORE_PATTERNS)
    stretch_score, stretch_label = _match(title, _STRETCH_PATTERNS)
    sk_score, matched_skills = _skill_score(description)

    # Company-type bonus
    if category in _QUANT_CATEGORIES:
        cat_bonus = 20
    elif category in _FINANCE_CATEGORIES:
        cat_bonus = 12
    elif category == "vc":
        cat_bonus = 8
    else:
        cat_bonus = 4

    total = core_score + stretch_score + cat_bonus + sk_score

    # Classification: core if title strongly matches, or if at quant/trading firm with decent score
    if core_score >= 30:
        match_category = "core"
    elif stretch_score > 0 and category in _QUANT_CATEGORIES and total >= 40:
        match_category = "core"
    elif total >= 25:
        match_category = "stretch"
    else:
        match_category = "stretch"

    # Human-readable match reason (one line)
    reasons = []
    if core_label:
        reasons.append(f'title: “{core_label}”')
    elif stretch_label:
        reasons.append(f'adjacent title: “{stretch_label}”')
    if category in _QUANT_CATEGORIES:
        reasons.append("target firm type")
    elif category in _FINANCE_CATEGORIES:
        reasons.append("finance firm")
    if matched_skills:
        top = matched_skills[:3]
        reasons.append(f"skills: {', '.join(top)}")
    match_reason = " · ".join(reasons) if reasons else "matches profile"

    return {
        **job,
        "score": min(100, total),
        "match_category": match_category,
        "match_reason": match_reason,
    }


def classify_and_rank(jobs: list[dict]) -> list[dict]:
    scored = [score_job(j) for j in jobs]
    scored.sort(key=lambda j: (-j["score"], j.get("posted_at", "")))
    return scored
