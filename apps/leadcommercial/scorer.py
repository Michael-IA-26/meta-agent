from datetime import date, datetime

SCORING_RULES = {
    "creation": 100,
    "rattrapage": 80,
    "fiscal": 80,
    "intention": 60,
}

DEPT_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]

FORMES_PRIORITAIRES = ["5710", "5720", "5499"]  # SAS, SASU, EURL

NAF_RESTAURATION = ["56.10A", "56.10B", "56.21Z", "56.29A", "56.29B", "56.30Z"]


def score_lead(company: dict, signal_type: str = "creation") -> dict:
    score = 0
    details = []

    # Signal de base
    base_score = SCORING_RULES.get(signal_type, 0)
    score += base_score
    details.append(f"Signal {signal_type}: +{base_score}")

    # Bonus restauration (secteur prioritaire JM Partners)
    code_naf = company.get("code_naf", "")
    if code_naf in NAF_RESTAURATION:
        score = min(score + 10, 100)
        details.append("Secteur restauration (prioritaire): +10")

    # Bonus creation tres recente (< 7 jours)
    date_creation = company.get("date_creation")
    if date_creation:
        try:
            if isinstance(date_creation, str):
                d = datetime.strptime(date_creation, "%Y-%m-%d").date()
            else:
                d = date_creation
            age_days = (date.today() - d).days
            if age_days <= 7:
                score = min(score + 10, 100)
                details.append(f"Creation tres recente ({age_days}j): +10")
            elif age_days <= 14:
                score = min(score + 5, 100)
                details.append(f"Creation recente ({age_days}j): +5")
        except ValueError:
            pass

    # Malus forme juridique non prioritaire
    forme = company.get("forme_juridique", "")
    if forme and forme not in FORMES_PRIORITAIRES:
        score = max(score - 10, 0)
        details.append(f"Forme juridique non prioritaire ({forme}): -10")

    # Verification departement IDF
    dept = company.get("dept", "")
    if dept not in DEPT_IDF:
        score = 0
        details.append(f"Hors IDF ({dept}): score = 0")

    return {
        "siren": company.get("siren"),
        "score": score,
        "signal_type": signal_type,
        "scoring_details": details,
        "qualified": score >= 50,
    }


def score_batch(companies: list, signal_type: str = "creation") -> list:
    results = []
    for company in companies:
        result = score_lead(company, signal_type)
        results.append(result)
        status = "QUALIFIE" if result["qualified"] else "rejete"
        print(
            f"  {company.get('denomination', 'N/A')} — score {result['score']} — {status}"
        )
    return results


if __name__ == "__main__":
    test_companies = [
        {
            "siren": "123456789",
            "denomination": "LE BON RESTO SAS",
            "forme_juridique": "5710",
            "code_naf": "56.10A",
            "dept": "75",
            "date_creation": datetime.now().strftime("%Y-%m-%d"),
        },
        {
            "siren": "987654321",
            "denomination": "DUPONT CONSULTING",
            "forme_juridique": "5499",
            "code_naf": "70.22Z",
            "dept": "92",
            "date_creation": "2026-04-01",
        },
        {
            "siren": "111222333",
            "denomination": "MARTIN SA",
            "forme_juridique": "5599",
            "code_naf": "62.01Z",
            "dept": "69",
            "date_creation": datetime.now().strftime("%Y-%m-%d"),
        },
    ]

    print("Test scoring LeadCommercial:")
    results = score_batch(test_companies)
    print()
    for r in results:
        print(f"  {r['siren']}: {r['scoring_details']}")
