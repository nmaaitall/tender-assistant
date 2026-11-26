"""Synthetic tender cases with known answers.

Each case lists the sentences of a tender document page by page and the values a
correct extraction must return. Fields set to None are not stated in the document.
"""

from __future__ import annotations

from typing import Any

FIELDS = (
    "reference",
    "work_category",
    "required_classification_grade",
    "min_registered_capital",
    "min_similar_projects",
    "min_similar_project_value",
    "experience_lookback_years",
    "min_years_experience",
    "submission_deadline",
    "bid_guarantee_amount",
)


def case(
    case_id: str,
    note: str,
    pages: list[list[str]],
    expected: dict[str, Any],
) -> dict[str, Any]:
    missing = set(FIELDS) - set(expected)
    if missing:
        raise ValueError(f"{case_id} does not set {sorted(missing)}")
    return {"id": case_id, "note": note, "pages": pages, "expected": expected}


CASES = [
    case(
        "c01_baseline",
        "Same wording as the test fixture.",
        [
            [
                "بلدية الزرقاء",
                "كراسة الشروط والمواصفات",
                "عطاء رقم ZM-2026-014",
                "إنشاء مبنى خدمات بلدية في منطقة الزرقاء الجديدة",
                "آخر موعد لتقديم العروض: الساعة الثانية عشرة ظهراً من يوم 2026/10/15",
            ],
            [
                "يحق الاشتراك في هذا العطاء للمقاولين الأردنيين المصنفين لدى دائرة العطاءات "
                "الحكومية في مجال الأبنية بالفئة الثالثة أو أعلى.",
                "يجب ألا يقل رأس المال المسجل للمقاول عن 100,000 دينار أردني.",
                "يشترط أن تكون لدى المقاول خبرة لا تقل عن ثلاث سنوات في تنفيذ أعمال الأبنية.",
                "يشترط أن يكون المقاول قد نفذ مشروعين مماثلين على الأقل خلال السنوات الخمس "
                "الأخيرة، لا تقل قيمة كل منهما عن 250,000 دينار أردني.",
            ],
            ["يقدم المقاول مع عرضه كفالة دخول عطاء بقيمة 20,000 دينار أردني."],
        ],
        {
            "reference": "ZM-2026-014",
            "work_category": "buildings",
            "required_classification_grade": 3,
            "min_registered_capital": 100000,
            "min_similar_projects": 2,
            "min_similar_project_value": 250000,
            "experience_lookback_years": 5,
            "min_years_experience": 3,
            "submission_deadline": "2026-10-15",
            "bid_guarantee_amount": 20000,
        },
    ),
    case(
        "c02_roads",
        "Roads, grade 2, larger amounts, seven-year window.",
        [
            [
                "وزارة الأشغال العامة والإسكان",
                "دعوة عطاء رقم MPWH/R/2026/33",
                "صيانة وتأهيل طريق المفرق - الصفاوي",
                "تقدم العروض في موعد أقصاه يوم الأحد الموافق 2026/12/06 الساعة الواحدة ظهراً.",
            ],
            [
                "شروط الاشتراك:",
                "أن يكون المقاول مصنفاً في مجال الطرق بالفئة الثانية فما فوق.",
                "ألا يقل رأس المال المسجل عن 500,000 دينار أردني.",
                "أن يكون قد نفذ ثلاثة مشاريع طرق مماثلة خلال السنوات السبع الأخيرة، "
                "قيمة كل منها 400,000 دينار أردني على الأقل.",
                "خبرة في أعمال الطرق لا تقل عن خمس سنوات.",
            ],
            ["قيمة كفالة دخول العطاء 35,000 دينار أردني صادرة عن بنك أردني."],
        ],
        {
            "reference": "MPWH/R/2026/33",
            "work_category": "roads",
            "required_classification_grade": 2,
            "min_registered_capital": 500000,
            "min_similar_projects": 3,
            "min_similar_project_value": 400000,
            "experience_lookback_years": 7,
            "min_years_experience": 5,
            "submission_deadline": "2026-12-06",
            "bid_guarantee_amount": 35000,
        },
    ),
    case(
        "c03_water_small",
        "Water works, grade 4, experience written as a dual (سنتين), one project.",
        [
            [
                "سلطة المياه",
                "عطاء رقم WAJ-SW-2026-07",
                "تمديد خطوط مياه فرعية في لواء الرصيفة",
                "آخر موعد لإيداع العروض 2026/11/30",
            ],
            [
                "يشترط أن يكون المقاول مصنفاً في مجال المياه والصرف الصحي بالفئة الرابعة أو أعلى.",
                "رأس المال المسجل لا يقل عن 75,000 دينار.",
                "خبرة لا تقل عن سنتين في أعمال المياه.",
                "تنفيذ مشروع واحد مماثل على الأقل خلال السنوات الخمس الماضية لا تقل قيمته "
                "عن 100,000 دينار.",
                "كفالة دخول العطاء 5,000 دينار أردني.",
            ],
        ],
        {
            "reference": "WAJ-SW-2026-07",
            "work_category": "water_and_sewerage",
            "required_classification_grade": 4,
            "min_registered_capital": 75000,
            "min_similar_projects": 1,
            "min_similar_project_value": 100000,
            "experience_lookback_years": 5,
            "min_years_experience": 2,
            "submission_deadline": "2026-11-30",
            "bid_guarantee_amount": 5000,
        },
    ),
    case(
        "c04_electromech_large",
        "Electromechanical, grade 1, very large amounts.",
        [
            [
                "دائرة العطاءات الحكومية",
                "عطاء رقم GTD/EM/2026/112",
                "توريد وتركيب أنظمة التكييف المركزي لمستشفى الأمير حمزة",
                "آخر موعد لتقديم العروض 2027/01/14",
            ],
            [
                "يقتصر الاشتراك على المقاولين المصنفين في مجال الأعمال الكهروميكانيكية "
                "بالفئة الأولى.",
                "رأس المال المسجل لا يقل عن 2,000,000 دينار أردني.",
                "خبرة لا تقل عن عشر سنوات في الأعمال الكهروميكانيكية.",
                "تنفيذ مشروعين مماثلين خلال آخر خمس سنوات قيمة كل منهما لا تقل عن "
                "1,500,000 دينار أردني.",
            ],
            ["كفالة دخول العطاء: 120,000 دينار أردني سارية لمدة 120 يوماً."],
        ],
        {
            "reference": "GTD/EM/2026/112",
            "work_category": "electromechanical",
            "required_classification_grade": 1,
            "min_registered_capital": 2000000,
            "min_similar_projects": 2,
            "min_similar_project_value": 1500000,
            "experience_lookback_years": 5,
            "min_years_experience": 10,
            "submission_deadline": "2027-01-14",
            "bid_guarantee_amount": 120000,
        },
    ),
    case(
        "c05_missing_fields",
        "Small job that states no capital and no project history. Those fields must stay empty.",
        [
            [
                "بلدية السلط الكبرى",
                "عطاء رقم SALT-B-2026-19",
                "ترميم واجهات مبنى البلدية القديم",
                "آخر موعد لتقديم العروض 2026/12/10",
            ],
            [
                "يحق الاشتراك للمقاولين المصنفين في مجال الأبنية بالفئة الخامسة أو أعلى.",
                "أن تكون لدى المقاول خبرة لا تقل عن سنتين.",
                "تقدم كفالة دخول عطاء بقيمة 2,500 دينار أردني.",
            ],
        ],
        {
            "reference": "SALT-B-2026-19",
            "work_category": "buildings",
            "required_classification_grade": 5,
            "min_registered_capital": None,
            "min_similar_projects": None,
            "min_similar_project_value": None,
            "experience_lookback_years": None,
            "min_years_experience": 2,
            "submission_deadline": "2026-12-10",
            "bid_guarantee_amount": 2500,
        },
    ),
    case(
        "c06_distractors",
        "Other amounts sit next to the real ones: performance bond, insurance, delay penalty.",
        [
            [
                "بلدية إربد الكبرى",
                "عطاء رقم IRB-2026-41",
                "إنشاء مدرسة أساسية في منطقة الحصن",
                "آخر موعد لتقديم العروض 2026/12/20",
            ],
            [
                "يشترط تصنيف المقاول في مجال الأبنية بالفئة الثالثة أو أعلى.",
                "يجب ألا يقل رأس المال المسجل للمقاول عن 150,000 دينار أردني.",
                "تنفيذ مشروعين مماثلين خلال السنوات الخمس الأخيرة لا تقل قيمة كل منهما "
                "عن 300,000 دينار أردني.",
                "خبرة لا تقل عن أربع سنوات في أعمال الأبنية.",
            ],
            [
                "يقدم المقاول الفائز كفالة حسن تنفيذ بقيمة 90,000 دينار أردني.",
                "يلتزم المقاول بتأمين ضد الغير بقيمة 50,000 دينار أردني.",
                "تفرض غرامة تأخير مقدارها 200 دينار عن كل يوم تأخير.",
                "كفالة دخول العطاء 15,000 دينار أردني.",
            ],
        ],
        {
            "reference": "IRB-2026-41",
            "work_category": "buildings",
            "required_classification_grade": 3,
            "min_registered_capital": 150000,
            "min_similar_projects": 2,
            "min_similar_project_value": 300000,
            "experience_lookback_years": 5,
            "min_years_experience": 4,
            "submission_deadline": "2026-12-20",
            "bid_guarantee_amount": 15000,
        },
    ),
    case(
        "c07_list_format",
        "Requirements written as label: value lines.",
        [
            [
                "أمانة عمان الكبرى",
                "رقم العطاء: GAM-RD-2026-88",
                "موضوع العطاء: إعادة تعبيد شوارع في منطقة ماركا",
                "تاريخ الإغلاق: 2026/12/15",
            ],
            [
                "المجال المطلوب: الطرق",
                "الفئة المطلوبة: الثالثة",
                "الحد الأدنى لرأس المال المسجل: 250,000 دينار",
                "عدد المشاريع المماثلة المطلوبة: 2",
                "الحد الأدنى لقيمة المشروع المماثل: 200,000 دينار",
                "الفترة الزمنية للمشاريع المماثلة: آخر 5 سنوات",
                "الحد الأدنى لسنوات الخبرة: 6",
                "قيمة كفالة دخول العطاء: 12,000 دينار",
            ],
        ],
        {
            "reference": "GAM-RD-2026-88",
            "work_category": "roads",
            "required_classification_grade": 3,
            "min_registered_capital": 250000,
            "min_similar_projects": 2,
            "min_similar_project_value": 200000,
            "experience_lookback_years": 5,
            "min_years_experience": 6,
            "submission_deadline": "2026-12-15",
            "bid_guarantee_amount": 12000,
        },
    ),
    case(
        "c08_amounts_in_words",
        "Amounts given as digits followed by words, the usual legal style.",
        [
            [
                "وزارة المياه والري",
                "عطاء رقم MWI-2026-05",
                "إنشاء محطة ضخ في منطقة الأزرق",
                "آخر موعد لتقديم العروض 2027/01/05",
            ],
            [
                "يشترط أن يكون المقاول مصنفاً في مجال المياه والصرف الصحي بالفئة الثانية.",
                "ألا يقل رأس المال المسجل عن (300,000) ثلاثمائة ألف دينار أردني.",
                "أن يكون قد نفذ مشروعين مماثلين خلال السنوات العشر الأخيرة لا تقل قيمة كل "
                "منهما عن (500,000) خمسمائة ألف دينار أردني.",
                "خبرة لا تقل عن ثماني سنوات.",
                "كفالة دخول العطاء (25,000) خمسة وعشرون ألف دينار أردني.",
            ],
        ],
        {
            "reference": "MWI-2026-05",
            "work_category": "water_and_sewerage",
            "required_classification_grade": 2,
            "min_registered_capital": 300000,
            "min_similar_projects": 2,
            "min_similar_project_value": 500000,
            "experience_lookback_years": 10,
            "min_years_experience": 8,
            "submission_deadline": "2027-01-05",
            "bid_guarantee_amount": 25000,
        },
    ),
    case(
        "c09_other_works",
        "Field outside the four main ones.",
        [
            [
                "بلدية مادبا الكبرى",
                "عطاء رقم MDB-OW-2026-03",
                "أعمال تنسيق حدائق وزراعة أشجار",
                "آخر موعد لتقديم العروض 2026/12/01",
            ],
            [
                "يحق الاشتراك للمقاولين المصنفين في مجال الأعمال الأخرى بالفئة الرابعة أو أعلى.",
                "رأس المال المسجل لا يقل عن 50,000 دينار أردني.",
                "خبرة لا تقل عن ثلاث سنوات.",
                "كفالة دخول العطاء 3,000 دينار أردني.",
            ],
        ],
        {
            "reference": "MDB-OW-2026-03",
            "work_category": "other_works",
            "required_classification_grade": 4,
            "min_registered_capital": 50000,
            "min_similar_projects": None,
            "min_similar_project_value": None,
            "experience_lookback_years": None,
            "min_years_experience": 3,
            "submission_deadline": "2026-12-01",
            "bid_guarantee_amount": 3000,
        },
    ),
    case(
        "c10_arabic_digits",
        "Numbers written with Arabic-Indic digits.",
        [
            [
                "بلدية العقبة",
                "عطاء رقم AQB-2026-22",
                "إنشاء مركز خدمات بلدية",
                "آخر موعد لتقديم العروض ٢٠٢٦/١٢/٢٤",
            ],
            [
                "يشترط أن يكون المقاول مصنفاً في مجال الأبنية بالفئة الرابعة أو أعلى.",
                "ألا يقل رأس المال المسجل عن ١٢٠,٠٠٠ دينار أردني.",
                "تنفيذ مشروع مماثل واحد خلال السنوات الخمس الأخيرة لا تقل قيمته عن "
                "١٨٠,٠٠٠ دينار أردني.",
                "خبرة لا تقل عن ثلاث سنوات.",
                "كفالة دخول العطاء ٧,٥٠٠ دينار أردني.",
            ],
        ],
        {
            "reference": "AQB-2026-22",
            "work_category": "buildings",
            "required_classification_grade": 4,
            "min_registered_capital": 120000,
            "min_similar_projects": 1,
            "min_similar_project_value": 180000,
            "experience_lookback_years": 5,
            "min_years_experience": 3,
            "submission_deadline": "2026-12-24",
            "bid_guarantee_amount": 7500,
        },
    ),
    case(
        "c11_spread_over_pages",
        "Each requirement on a different page, with unrelated text in between.",
        [
            [
                "وزارة التربية والتعليم",
                "عطاء رقم MOE-2026-61",
                "إضافة غرف صفية لمدرسة جرش الثانوية",
                "آخر موعد لتقديم العروض يوم الخميس الموافق 2026/12/03",
            ],
            [
                "تعليمات عامة: تعبأ جداول الكميات بالحبر وتوقع كل صفحة.",
                "يشترط أن يكون المقاول مصنفاً في مجال الأبنية بالفئة الرابعة أو أعلى.",
            ],
            [
                "مدة التنفيذ 240 يوماً تقويمياً.",
                "ألا يقل رأس المال المسجل للمقاول عن 90,000 دينار أردني.",
            ],
            [
                "خبرة لا تقل عن خمس سنوات في أعمال الأبنية.",
                "تنفيذ مشروعين مماثلين خلال السنوات الست الأخيرة لا تقل قيمة كل منهما عن "
                "120,000 دينار أردني.",
            ],
            ["كفالة دخول العطاء 6,000 دينار أردني."],
        ],
        {
            "reference": "MOE-2026-61",
            "work_category": "buildings",
            "required_classification_grade": 4,
            "min_registered_capital": 90000,
            "min_similar_projects": 2,
            "min_similar_project_value": 120000,
            "experience_lookback_years": 6,
            "min_years_experience": 5,
            "submission_deadline": "2026-12-03",
            "bid_guarantee_amount": 6000,
        },
    ),
    case(
        "c12_million",
        "Amount written as a word (مليون) next to digits, ten-year window.",
        [
            [
                "وزارة الصحة",
                "عطاء رقم MOH-B-2026-09",
                "إنشاء مستشفى الطفيلة الحكومي الجديد",
                "آخر موعد لتقديم العروض 2027/02/01",
            ],
            [
                "يحق الاشتراك للمقاولين المصنفين في مجال الأبنية بالفئة الأولى.",
                "رأس المال المسجل لا يقل عن 3,000,000 دينار أردني (ثلاثة ملايين دينار).",
                "تنفيذ مشروعين مماثلين خلال السنوات العشر الأخيرة لا تقل قيمة كل منهما عن "
                "10,000,000 دينار أردني (عشرة ملايين دينار).",
                "خبرة لا تقل عن خمس عشرة سنة.",
                "كفالة دخول العطاء 250,000 دينار أردني.",
            ],
        ],
        {
            "reference": "MOH-B-2026-09",
            "work_category": "buildings",
            "required_classification_grade": 1,
            "min_registered_capital": 3000000,
            "min_similar_projects": 2,
            "min_similar_project_value": 10000000,
            "experience_lookback_years": 10,
            "min_years_experience": 15,
            "submission_deadline": "2027-02-01",
            "bid_guarantee_amount": 250000,
        },
    ),
]
