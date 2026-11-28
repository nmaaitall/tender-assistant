"""Synthetic tender descriptions for training a work category classifier.

Each example is a tender title and a short scope, written from templates. To test
generalization rather than memory, the work items, title frames and scope details
are split into disjoint train, validation and test pools: the test set only holds
work items the model never saw. Many scopes also mention a secondary trade (a
building with electrical works, a road with rainwater drains), so a single
keyword is not enough to decide.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from app.domain.enums import WorkCategory

ITEMS: dict[WorkCategory, list[str]] = {
    WorkCategory.ROADS: [
        "تعبيد شوارع داخلية",
        "إعادة تأهيل طريق رئيسي",
        "توسعة تقاطع مروري",
        "إنشاء جسر مشاة",
        "صيانة الطرق الزراعية",
        "تنفيذ أرصفة وأطاريف",
        "دهان خطوط المرور على الشوارع",
        "إنشاء دوار مروري",
        "فتح طريق جديد",
        "تسوية الطرق الترابية",
        "تركيب حواجز معدنية على جوانب الطريق",
        "إعادة تعبيد الطبقة السطحية للشوارع",
        "إنشاء مواقف سيارات معبدة",
        "معالجة الحفر والتشققات في الشوارع",
        "رصف الممرات بالحجر المتداخل",
        "توسعة الطريق الدائري",
        "إنشاء نفق مروري",
        "تنفيذ مطبات وشواخص مرورية",
        "إنشاء طريق خدمات موازي",
        "تأهيل مسارب الطريق الصحراوي",
    ],
    WorkCategory.BUILDINGS: [
        "إنشاء مبنى مدرسة أساسية",
        "توسعة مركز صحي شامل",
        "بناء قاعة متعددة الأغراض",
        "إنشاء مبنى إداري للبلدية",
        "صيانة وترميم مبنى حكومي",
        "إنشاء سور حول مدرسة",
        "تشطيبات داخلية لمبنى",
        "إنشاء مستودع بهيكل خرساني",
        "إضافة طابق لمبنى قائم",
        "إنشاء غرف صفية إضافية",
        "ترميم بيت تراثي",
        "إنشاء مسجد",
        "بناء مركز شباب",
        "إنشاء مكاتب في السوق المركزي",
        "عزل أسطح المباني",
        "أعمال القصارة والدهان للمباني",
        "إنشاء مجمع محاكم",
        "إنشاء حضانة أطفال",
        "إنشاء مبنى مركز دفاع مدني",
        "ترميم الواجهات الحجرية للمباني",
    ],
    WorkCategory.ELECTROMECHANICAL: [
        "توريد وتركيب مصاعد",
        "تركيب أنظمة تكييف مركزي",
        "تركيب أنظمة إنذار ومكافحة حريق",
        "توريد وتركيب مولدات كهربائية احتياطية",
        "تمديدات كهربائية ولوحات توزيع",
        "إنارة الشوارع بوحدات موفرة للطاقة",
        "تركيب أنظمة طاقة شمسية",
        "صيانة المضخات والمحركات في محطة ضخ",
        "تركيب أنظمة تدفئة مركزية",
        "تركيب كاميرات مراقبة وشبكات اتصال",
        "تركيب سلالم كهربائية متحركة",
        "توريد وتركيب محولات كهربائية",
        "تركيب أنظمة التهوية والشفط",
        "صيانة الأنظمة الميكانيكية لمستشفى",
        "تركيب نظام تحكم مركزي بالمبنى",
        "تركيب غرف تبريد",
        "تمديد كوابل ضغط متوسط",
        "تركيب مضخات حريق",
        "تركيب وحدات معالجة الهواء",
        "تحديث لوحات التحكم الكهربائية",
    ],
    WorkCategory.WATER_AND_SEWERAGE: [
        "تمديد خطوط مياه رئيسية",
        "إنشاء شبكة صرف صحي",
        "إنشاء خزان مياه خرساني",
        "تأهيل محطة معالجة مياه عادمة",
        "حفر بئر ارتوازي",
        "استبدال عدادات المياه",
        "إنشاء خط ناقل للمياه",
        "تمديد خطوط تصريف مياه الأمطار",
        "صيانة المناهل",
        "ربط المنازل بشبكة الصرف الصحي",
        "إنشاء محطة رفع للمياه العادمة",
        "تأهيل شبكات المياه للحد من الفاقد",
        "تمديد خطوط ري",
        "تنظيف خطوط الصرف",
        "إنشاء خزان مياه علوي",
        "استبدال أنابيب المياه القديمة",
        "إنشاء خط مياه لتزويد قرية",
        "توسعة شبكة الصرف الصحي",
        "تأهيل الآبار الجوفية",
        "إنشاء بركة تجميع مياه",
    ],
    WorkCategory.OTHER_WORKS: [
        "تنسيق حدائق وزراعة أشجار",
        "إنشاء ملاعب رياضية بالعشب الصناعي",
        "إنشاء جدران استنادية",
        "أعمال حفر وردم وتسوية أراض",
        "هدم وإزالة منشآت قديمة",
        "تركيب ألعاب أطفال في الحدائق",
        "إنشاء ممرات مشاة في متنزه",
        "تسييج أراض حكومية",
        "تجميل مداخل المدينة",
        "إنشاء جلسات ومظلات في حديقة عامة",
        "إزالة الأنقاض والمخلفات",
        "أعمال تحريج وزراعة غابات",
        "ردم وتسوية مكب نفايات",
        "تركيب لوحات إرشادية سياحية",
        "إنشاء مسار سياحي للمشي",
        "تأهيل ساحة عامة",
        "زراعة الجزر الوسطية",
        "إنشاء ملعب كرة سلة",
        "حماية المنحدرات من الانهيار",
        "تأهيل موقع أثري للزوار",
    ],
}

DETAILS: dict[WorkCategory, list[str]] = {
    WorkCategory.ROADS: [
        "فرش طبقة أساس حصمة وطبقة إسفلت",
        "أعمال الحفر والتسوية للمسار",
        "الدهانات المرورية وعيون القطط",
        "تركيب الأطاريف والجزر الوسطية",
        "دحل الطبقات حسب المواصفات",
        "تحويلات مرورية مؤقتة أثناء العمل",
        "قشط الإسفلت القديم",
        "إشارات وشواخص مرورية",
    ],
    WorkCategory.BUILDINGS: [
        "أعمال الخرسانة المسلحة للهيكل",
        "أعمال الطوب والقصارة",
        "تبليط الأرضيات",
        "أعمال النجارة والألمنيوم",
        "الدهانات الداخلية والخارجية",
        "تكسية الواجهات بالحجر",
        "عزل الأساسات والأسطح",
        "الأعمال المعمارية والإنشائية",
    ],
    WorkCategory.ELECTROMECHANICAL: [
        "التمديدات الكهربائية والإنارة",
        "لوحات التوزيع والقواطع",
        "التمديدات الميكانيكية",
        "أنظمة التحكم والتشغيل",
        "الفحص والتشغيل التجريبي للأنظمة",
        "التمديدات الصحية للمبنى",
        "الصيانة الدورية للمعدات",
        "توريد المعدات وفق المواصفات الفنية",
    ],
    WorkCategory.WATER_AND_SEWERAGE: [
        "توريد وتمديد أنابيب البولي إيثيلين",
        "إنشاء غرف المحابس",
        "فحص الضغط للخطوط",
        "إعادة الشيء إلى أصله بعد الحفر",
        "تركيب المحابس والقطع الخاصة",
        "تعقيم الخطوط قبل التشغيل",
        "إنشاء المناهل الخرسانية",
        "الوصلات المنزلية",
    ],
    WorkCategory.OTHER_WORKS: [
        "أعمال الزراعة والري بالتنقيط",
        "توريد التربة الزراعية",
        "أعمال التسييج",
        "أعمال الحفر والردم",
        "تركيب المقاعد وسلال النفايات",
        "أعمال الإنارة التجميلية",
        "تسوية الموقع وإزالة المخلفات",
        "أعمال الحجر والجدران الحجرية",
    ],
}

TITLES = [
    "عطاء {item} في {place}",
    "{item} - {entity}",
    "مشروع {item} لصالح {entity} في {place}",
    "دعوة لتقديم عروض: {item} في {place}",
    "عطاء رقم {number} الخاص بـ {item}",
    "{item} في منطقة {place}",
    "استدراج عروض {item} لصالح {entity}",
    "مناقصة عامة: {item} في {place}",
    "مشروع {item} - المرحلة {phase}",
]

SCOPES = [
    "يشمل نطاق العمل {item} ويتضمن {detail} و{detail2}.",
    "تتضمن الأعمال المطلوبة {detail} و{detail2} ضمن مشروع {item}.",
    "يقوم المقاول بتنفيذ {item}، ويشمل ذلك {detail} و{detail2}.",
    "الأعمال: {item}؛ {detail}؛ {detail2}.",
    "نطاق العطاء {item} بما في ذلك {detail} وأي أعمال لازمة لـ {detail2}.",
]

SECONDARY = [
    "بالإضافة إلى {other} المرافقة.",
    "كما يشمل العطاء جزءا محدودا من {other}.",
    "وتنفذ {other} من قبل مقاول فرعي معتمد.",
]

GENERAL = [
    "مدة التنفيذ مئة وعشرون يوما من تاريخ أمر المباشرة.",
    "يلتزم المقاول بمتطلبات السلامة العامة في الموقع.",
    "تقدم العروض في مغلفين فني ومالي.",
    "يجب أن تكون المواد مطابقة للمواصفات الأردنية.",
    "يتحمل المقاول نفقات الفحوصات المخبرية.",
]

PLACES = [
    "الزرقاء",
    "الرصيفة",
    "إربد",
    "المفرق",
    "جرش",
    "عجلون",
    "السلط",
    "مادبا",
    "الكرك",
    "الطفيلة",
    "معان",
    "العقبة",
    "الأزرق",
    "الهاشمية",
    "الضليل",
    "الرمثا",
    "دير علا",
    "الشونة الجنوبية",
    "سحاب",
    "ناعور",
]
ENTITIES = [
    "بلدية الزرقاء",
    "وزارة الأشغال العامة والإسكان",
    "سلطة المياه",
    "وزارة التربية والتعليم",
    "وزارة الصحة",
    "أمانة عمان الكبرى",
    "بلدية إربد الكبرى",
    "سلطة منطقة العقبة الاقتصادية",
    "وزارة الشباب",
    "شركة مياه اليرموك",
    "وزارة الأوقاف",
    "وزارة السياحة والآثار",
]
LABELS = [c.value for c in WorkCategory]


@dataclass(frozen=True)
class Example:
    text: str
    label: str


def _split(items: list, rng: random.Random, fractions=(0.7, 0.15)) -> dict[str, list]:
    shuffled = items[:]
    rng.shuffle(shuffled)
    a = round(len(shuffled) * fractions[0])
    b = a + max(1, round(len(shuffled) * fractions[1]))
    return {"train": shuffled[:a], "val": shuffled[a:b], "test": shuffled[b:]}


def build(per_class: dict[str, int] | None = None, seed: int = 7) -> dict[str, list[Example]]:
    """Returns train, val and test examples; no work item or frame is shared between them."""
    per_class = per_class or {"train": 300, "val": 60, "test": 80}
    rng = random.Random(seed)
    items = {c: _split(v, rng) for c, v in ITEMS.items()}
    details = {c: _split(v, rng, (0.5, 0.25)) for c, v in DETAILS.items()}
    titles = _split(TITLES, rng, (0.56, 0.22))
    scopes = _split(SCOPES, rng, (0.6, 0.2))

    data: dict[str, list[Example]] = {}
    for split, count in per_class.items():
        examples = []
        for category in WorkCategory:
            for _ in range(count):
                examples.append(
                    Example(
                        _text(rng, category, split, items, details, titles, scopes),
                        category.value,
                    )
                )
        rng.shuffle(examples)
        data[split] = examples
    return data


def _text(rng, category, split, items, details, titles, scopes) -> str:
    item = rng.choice(items[category][split])
    pool = details[category][split] or DETAILS[category]
    detail, detail2 = rng.sample(pool, 2) if len(pool) > 1 else (pool[0], pool[0])
    title = rng.choice(titles[split]).format(
        item=item,
        place=rng.choice(PLACES),
        entity=rng.choice(ENTITIES),
        number=f"{rng.randint(1, 99)}/{rng.choice([2025, 2026])}",
        phase=rng.choice(["الأولى", "الثانية", "الثالثة"]),
    )
    parts = [title, rng.choice(scopes[split]).format(item=item, detail=detail, detail2=detail2)]
    if rng.random() < 0.4:
        other = rng.choice([c for c in WorkCategory if c is not category])
        parts.append(rng.choice(SECONDARY).format(other=rng.choice(DETAILS[other])))
    parts += rng.sample(GENERAL, rng.randint(0, 2))
    return "\n".join(parts)
