from typing import Any


class FakeLLM:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        self.calls.append((system, user))
        return self.response


# What a model returns for tests/fixtures/sample_tender.pdf. Quotes are written the
# way a model writes them, with the lam-alef ligature corrected.
SAMPLE_RESPONSE: dict[str, Any] = {
    "fields": {
        "reference": {"value": "ZM-2026-014", "page": 1, "quote": "عطاء رقم ZM-2026-014"},
        "title": {
            "value": "إنشاء مبنى خدمات بلدية في منطقة الزرقاء الجديدة",
            "page": 1,
            "quote": "إنشاء مبنى خدمات بلدية في منطقة الزرقاء الجديدة",
        },
        "work_category": {
            "value": "buildings",
            "page": 2,
            "quote": "مجال الأبنية بالفئة الثالثة أو أعلى",
        },
        "required_classification_grade": {
            "value": 3,
            "page": 2,
            "quote": "مجال الأبنية بالفئة الثالثة أو أعلى",
        },
        "min_registered_capital": {
            "value": 100000,
            "page": 2,
            "quote": "يجب ألا يقل رأس المال المسجل للمقاول عن 100,000",
        },
        "min_years_experience": {
            "value": 3,
            "page": 2,
            "quote": "خبرة لا تقل عن ثلاث سنوات في تنفيذ أعمال الأبنية",
        },
        "min_similar_projects": {
            "value": 2,
            "page": 2,
            "quote": "نفذ مشروعين مماثلين على الأقل خلال السنوات الخمس الأخيرة",
        },
        "experience_lookback_years": {
            "value": 5,
            "page": 2,
            "quote": "نفذ مشروعين مماثلين على الأقل خلال السنوات الخمس الأخيرة",
        },
        "min_similar_project_value": {
            "value": 250000,
            "page": 2,
            "quote": "لا تقل قيمة كل منهما عن 250,000",
        },
        "submission_deadline": {
            "value": "2026-10-15",
            "page": 1,
            "quote": "آخر موعد لتقديم العروض: الساعة الثانية عشرة ظهرا من يوم 2026/10/15",
        },
        "bid_guarantee_amount": {
            "value": 20000,
            "page": 3,
            "quote": "يقدم المقاول مع عرضه كفالة دخول عطاء بقيمة 20,000",
        },
    },
    "required_documents": [
        {
            "name": "شهادة تصنيف سارية المفعول",
            "page": 4,
            "quote": "شهادة تصنيف سارية المفعول صادرة عن دائرة العطاءات الحكومية",
        },
        {
            "name": "رخصة مهن سارية المفعول",
            "page": 4,
            "quote": "رخصة مهن سارية المفعول",
        },
    ],
}
