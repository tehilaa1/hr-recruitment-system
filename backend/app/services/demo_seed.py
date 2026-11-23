"""Sample data for the public demo workspace.

Used by ``scripts/seed_demo_data.py`` and ``POST /api/admin/demo/reset``.

Everything is written through the normal tenant-scoped FirestoreService
methods with ``owner_id = DEMO_TENANT_ID`` and validated by the same Pydantic
models as the API, so the seed can never write into another workspace.

Idempotent: ``seed_demo`` does nothing if the demo workspace already has data;
``reset_demo`` wipes the demo workspace (only it) and seeds it again.

The sample CVs are small Hebrew PDFs committed under app/demo_assets/cvs/
(regenerate them with scripts/generate_demo_cvs.py).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.models.budget import AnnualBudgetCreate, BudgetEventCreate, ExpenseCreate
from app.models.candidate import CandidateManualBase
from app.models.job import JobCreate
from app.models.maternity import MaternityLeaveCreate, MaternitySettings
from app.services.cv_file_service import CvFile, build_cv_file
from app.services.firestore_service import FirestoreService, check_owner_id

logger = logging.getLogger(__name__)

CV_ASSETS_DIR = Path(__file__).resolve().parents[1] / "demo_assets" / "cvs"


# ------------------------------------------------------------------ #
# People (each has a CV: app/demo_assets/cvs/{key}.pdf)               #
# ------------------------------------------------------------------ #


@dataclass(frozen=True)
class DemoPerson:
    key: str
    full_name: str
    family_name: str
    phone: str
    email: str
    address: str
    profession: str
    years_of_experience: int
    summary: str  # CV "about" paragraph
    experience: tuple[tuple[str, str, str], ...]  # (years, role, company)
    education: tuple[str, ...]
    skills: tuple[str, ...]

    @property
    def cv_file_name(self) -> str:
        return f"קורות חיים - {self.full_name} {self.family_name}.pdf"

    def record(self) -> dict:
        return CandidateManualBase(
            full_name=self.full_name,
            family_name=self.family_name,
            phone=self.phone,
            email=self.email,
            address=self.address,
            profession=self.profession,
            years_of_experience=self.years_of_experience,
        ).model_dump(exclude={"referred_by"})


PEOPLE: tuple[DemoPerson, ...] = (
    DemoPerson(
        "noa_levi", "נועה", "לוי", "050-1234501", "noa.levi@example.com", "תל אביב",
        "מפתחת Full Stack", 6,
        "מפתחת Full Stack עם ניסיון בבניית מערכות SaaS בענן, אוהבת קוד נקי ועבודת צוות.",
        (("2021–היום", "מפתחת Full Stack בכירה", "קלאודיפיי"),
         ("2018–2021", "מפתחת Backend", "דאטה-ליין")),
        ("B.Sc. מדעי המחשב, אוניברסיטת תל אביב",),
        ("Python", "React", "PostgreSQL", "AWS", "Docker"),
    ),
    DemoPerson(
        "yossi_cohen", "יוסי", "כהן", "052-2345602", "yossi.cohen@example.com", "רמת גן",
        "מפתח Backend", 4,
        "מפתח Backend שמתמחה בשירותי API ובמערכות עם עומסים גבוהים.",
        (("2022–היום", "מפתח Backend", "פיננס-טק בע\"מ"),
         ("2020–2022", "מפתח ג'וניור", "סייבר-נט")),
        ("B.Sc. הנדסת תוכנה, הטכניון",),
        ("Python", "FastAPI", "Redis", "Kafka"),
    ),
    DemoPerson(
        "michal_avraham", "מיכל", "אברהם", "054-3456703", "michal.avraham@example.com", "חיפה",
        "מעצבת UX/UI", 5,
        "מעצבת חוויית משתמש עם רקע במחקר משתמשים ובמערכות עיצוב.",
        (("2020–היום", "מעצבת מוצר", "סטודיו פיקסל"),
         ("2019–2020", "מעצבת UI", "אפליקו")),
        ("B.Des. תקשורת חזותית, שנקר",),
        ("Figma", "מחקר משתמשים", "Design Systems", "אב-טיפוס"),
    ),
    DemoPerson(
        "daniel_mizrahi", "דניאל", "מזרחי", "053-4567804", "daniel.mizrahi@example.com", "ראשון לציון",
        "איש DevOps", 7,
        "מהנדס DevOps שמוביל מעבר לענן, CI/CD ו-Kubernetes בארגונים בצמיחה.",
        (("2019–היום", "ראש צוות DevOps", "לוג'יסטיקס פרו"),
         ("2016–2019", "מהנדס מערכות", "נטוויז'ן")),
        ("הנדסאי תוכנה, מכללת אורט",),
        ("Kubernetes", "Terraform", "GitHub Actions", "GCP"),
    ),
    DemoPerson(
        "shira_peretz", "שירה", "פרץ", "058-5678905", "shira.peretz@example.com", "באר שבע",
        "רכזת גיוס", 3,
        "רכזת גיוס טכנולוגי עם ניסיון בגיוס מהיר למשרות פיתוח ומוצר.",
        (("2022–היום", "רכזת גיוס", "טאלנט-הב"),
         ("2021–2022", "רכזת משאבי אנוש", "מרכז הנגב")),
        ("B.A. פסיכולוגיה וניהול, אוניברסיטת בן גוריון",),
        ("גיוס טכנולוגי", "ראיונות", "LinkedIn Recruiter", "ATS"),
    ),
    DemoPerson(
        "avi_biton", "אבי", "ביטון", "050-6789006", "avi.biton@example.com", "אשדוד",
        "מנהל חשבונות", 9,
        "מנהל חשבונות סוג 3 עם ניסיון בהנהלת חשבונות של חברות טכנולוגיה.",
        (("2017–היום", "מנהל חשבונות ראשי", "גלובל סחר"),
         ("2014–2017", "מנהל חשבונות", "משרד רו\"ח לוינסון")),
        ("מנהל חשבונות סוג 3, לשכת מנהלי החשבונות",),
        ("Priority", "Excel מתקדם", "התאמות בנקים", "דוחות מע\"מ"),
    ),
    DemoPerson(
        "tamar_friedman", "תמר", "פרידמן", "052-7890107", "tamar.friedman@example.com", "ירושלים",
        "מנהלת מוצר", 8,
        "מנהלת מוצר B2B שהובילה השקות מוצר מאפס ועד אלפי לקוחות משלמים.",
        (("2019–היום", "מנהלת מוצר בכירה", "אדטק סולושנס"),
         ("2016–2019", "מנהלת מוצר", "מדיקל-סופט")),
        ("MBA, האוניברסיטה העברית", "B.Sc. תעשייה וניהול"),
        ("אסטרטגיית מוצר", "Jira", "ניתוח נתונים", "SQL"),
    ),
    DemoPerson(
        "eyal_shapira", "אייל", "שפירא", "054-8901208", "eyal.shapira@example.com", "הרצליה",
        "מפתח Frontend", 2,
        "מפתח Frontend צעיר ונלהב, בוגר קורס פיתוח אינטנסיבי ופרויקטים עצמאיים.",
        (("2023–היום", "מפתח Frontend", "סטארט-אפ שופ-איט"),),
        ("קורס Full Stack, אקדמיית קוד",),
        ("React", "TypeScript", "Tailwind", "Vite"),
    ),
    DemoPerson(
        "rivka_golan", "רבקה", "גולן", "053-9012309", "rivka.golan@example.com", "פתח תקווה",
        "מנהלת משרד", 11,
        "מנהלת משרד ותפעול עם ניסיון בניהול רכש, ספקים ואירועי חברה.",
        (("2015–היום", "מנהלת משרד ותפעול", "הייטק-זון"),
         ("2012–2015", "אדמיניסטרטורית", "קבוצת אלון")),
        ("תעודת ניהול משרד, מכללת ספיר",),
        ("ניהול ספקים", "רכש", "Office", "ארגון אירועים"),
    ),
    DemoPerson(
        "omer_katz", "עומר", "כץ", "058-0123410", "omer.katz@example.com", "נתניה",
        "אנליסט נתונים", 3,
        "אנליסט נתונים שאוהב להפוך נתונים גולמיים לתובנות עסקיות ברורות.",
        (("2022–היום", "אנליסט נתונים", "ריטייל-דאטה"),
         ("2021–2022", "אנליסט ג'וניור", "בנק הצפון")),
        ("B.A. כלכלה וסטטיסטיקה, אוניברסיטת בר אילן",),
        ("SQL", "Python", "Tableau", "BigQuery"),
    ),
    DemoPerson(
        "lior_ben_david", "ליאור", "בן דוד", "050-1112211", "lior.bendavid@example.com", "כפר סבא",
        "בודקת תוכנה QA", 5,
        "בודקת תוכנה עם ניסיון באוטומציה ובבדיקות מערכות ווב ומובייל.",
        (("2020–היום", "מהנדסת QA אוטומציה", "מובייל-פירסט"),
         ("2019–2020", "בודקת ידנית", "גיים-סטודיו")),
        ("קורס QA ואוטומציה, ג'ון ברייס",),
        ("Playwright", "Selenium", "Postman", "Jira"),
    ),
    DemoPerson(
        "hila_azulay", "הילה", "אזולאי", "052-2223312", "hila.azulay@example.com", "מודיעין",
        "מגייסת בכירה", 10,
        "מגייסת בכירה וראש צוות גיוס, מתמחה בגיוס מנהלים ותפקידי מפתח.",
        (("2018–היום", "ראש צוות גיוס", "פיפל-פירסט"),
         ("2014–2018", "מגייסת", "מנפאואר")),
        ("M.A. ייעוץ ארגוני, אוניברסיטת חיפה",),
        ("Headhunting", "Employer Branding", "ניהול צוות"),
    ),
    DemoPerson(
        "moshe_dahan", "משה", "דהן", "054-3334413", "moshe.dahan@example.com", "חולון",
        "תומך טכני", 1,
        "תומך טכני עם שירותיות גבוהה, לומד מהר ואוהב לפתור בעיות.",
        (("2024–היום", "תומך טכני", "קול-סנטר פלוס"),),
        ("בגרות מלאה במגמת מחשבים",),
        ("Windows", "Office 365", "שירות לקוחות"),
    ),
    DemoPerson(
        "yael_rosen", "יעל", "רוזן", "053-4445514", "yael.rosen@example.com", "גבעתיים",
        "מפתחת Backend", 3,
        "מפתחת Backend שעובדת עם Node.js ו-Python, עם רקע במתמטיקה.",
        (("2022–היום", "מפתחת Backend", "הלת'-טק"),
         ("2021–2022", "מתמחה בפיתוח", "אינטל")),
        ("B.Sc. מתמטיקה ומדעי המחשב, אוניברסיטת בר אילן",),
        ("Node.js", "Python", "MongoDB", "GraphQL"),
    ),
)

PEOPLE_BY_KEY = {p.key: p for p in PEOPLE}


# ------------------------------------------------------------------ #
# Jobs and applications: (person key, status, completed, referred by)  #
# ------------------------------------------------------------------ #

JOBS: tuple[tuple[dict, tuple[tuple[str, str, bool, str], ...]], ...] = (
    (
        {
            "job_title": "מפתח/ת Full Stack",
            "description": "פיתוח מערכת SaaS בענן: Python/FastAPI בצד השרת ו-React בצד הלקוח. "
                           "ניסיון של 3+ שנים, היכרות עם ענן – יתרון.",
            "interviewers": ["רונית שגיא", "אלון מור"],
            "interviewer_emails": ["ronit@example.com", "alon@example.com"],
            "interview_location": "משרדי החברה, תל אביב – קומה 12",
            "interview_type": "יחידני",
        },
        (
            ("noa_levi", "נשלח זימון", False, "אלון מור"),
            ("yossi_cohen", "לשלוח זימון", False, ""),
            ("yael_rosen", "לא טופל", False, "רונית שגיא"),
            ("eyal_shapira", "שלילי", True, ""),
        ),
    ),
    (
        {
            "job_title": "מהנדס/ת DevOps",
            "description": "הקמה ותחזוקה של תשתיות ענן, Kubernetes ו-CI/CD. כוננות חלקית.",
            "interviewers": ["אלון מור"],
            "interviewer_emails": ["alon@example.com"],
            "interview_location": "זום",
            "interview_type": "יחידני",
        },
        (
            ("daniel_mizrahi", "גויס/ה", True, "נועה לוי"),
            ("yossi_cohen", "לא עונה", False, ""),
        ),
    ),
    (
        {
            "job_title": "מעצב/ת מוצר UX/UI",
            "description": "עיצוב חוויית משתמש למוצר B2B, עבודה צמודה עם מנהלי מוצר ומפתחים.",
            "interviewers": ["תמר לוין"],
            "interviewer_emails": ["tamar.l@example.com"],
            "interview_location": "משרדי החברה, תל אביב – חדר ישיבות גדול",
            "interview_type": "מרוכז",
        },
        (
            ("michal_avraham", "נשלח זימון", False, ""),
            ("lior_ben_david", "לא רלוונטי", True, ""),
        ),
    ),
    (
        {
            "job_title": "רכז/ת גיוס",
            "description": "ניהול תהליכי גיוס מקצה לקצה, סינון קורות חיים ותיאום ראיונות.",
            "interviewers": ["הדס ברק"],
            "interviewer_emails": ["hadas@example.com"],
            "interview_location": "משרדי החברה, תל אביב",
            "interview_type": "מרוכז",
        },
        (
            ("shira_peretz", "לשלוח זימון", False, "הילה אזולאי"),
            ("hila_azulay", "לא טופל", False, ""),
            ("moshe_dahan", "שלילי", True, ""),
        ),
    ),
    (
        {
            "job_title": "מנהל/ת חשבונות",
            "description": "הנהלת חשבונות שוטפת, התאמות בנקים והכנת דוחות למשרד רואה החשבון.",
            "interviewers": ["רבקה גולן"],
            "interviewer_emails": ["rivka.g@example.com"],
            "interview_location": "משרדי החברה, פתח תקווה",
            "interview_type": "יחידני",
        },
        (
            ("avi_biton", "נשלח זימון", False, ""),
            ("rivka_golan", "לא עונה", False, ""),
        ),
    ),
)

# Talent pool: (person key, referred by). Some of them also applied to jobs.
POOL: tuple[tuple[str, str], ...] = (
    ("tamar_friedman", ""),
    ("omer_katz", "יוסי כהן"),
    ("noa_levi", ""),
    ("michal_avraham", "תמר פרידמן"),
    ("moshe_dahan", ""),
    ("hila_azulay", ""),
)


# ------------------------------------------------------------------ #
# Seeding                                                              #
# ------------------------------------------------------------------ #


def load_demo_cv(person: DemoPerson) -> Optional[CvFile]:
    path = CV_ASSETS_DIR / f"{person.key}.pdf"
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        logger.warning("Demo CV %s is missing (run scripts/generate_demo_cvs.py)", path.name)
        return None
    cv = build_cv_file(person.cv_file_name, data)
    if cv is None:
        logger.warning("Demo CV %s is not a valid PDF", path.name)
    return cv


def _budgets(today: date) -> list[tuple[dict, list[tuple[dict, list[dict]]]]]:
    """(year, [(event, [expenses])]) for the current and the previous year."""
    y = today.year
    return [
        (
            AnnualBudgetCreate(year=y - 1, total_budget=60000, notes="תקציב רווחה שנתי").model_dump(),
            [
                (
                    BudgetEventCreate(
                        name="ראש השנה", allocated_budget=15000, event_date=date(y - 1, 9, 10),
                        status="הסתיים", notes="מארזי שי לכל העובדים",
                    ).model_dump(mode="json"),
                    [
                        ExpenseCreate(item_name="מארזי דבש ויין", quantity=80, unit_price=120,
                                      status="שולם", invoice_reference="חשבונית 10234").model_dump(),
                        ExpenseCreate(item_name="משלוחים", total_price=1800, status="שולם").model_dump(),
                    ],
                ),
                (
                    BudgetEventCreate(
                        name="מסיבת חנוכה", allocated_budget=20000, event_date=date(y - 1, 12, 18),
                        status="הסתיים",
                    ).model_dump(mode="json"),
                    [
                        ExpenseCreate(item_name="קייטרינג", total_price=14500, status="שולם").model_dump(),
                        ExpenseCreate(item_name="די-ג'יי", total_price=3500, status="שולם").model_dump(),
                    ],
                ),
            ],
        ),
        (
            AnnualBudgetCreate(year=y, total_budget=75000, notes="כולל יום גיבוש שנתי").model_dump(),
            [
                (
                    BudgetEventCreate(
                        name="פורים", allocated_budget=8000, event_date=date(y, 3, 13),
                        status="הסתיים",
                    ).model_dump(mode="json"),
                    [
                        ExpenseCreate(item_name="משלוחי מנות", quantity=85, unit_price=65,
                                      status="שולם").model_dump(),
                        ExpenseCreate(item_name="תחפושות לתחרות", total_price=900,
                                      status="ישולם בהעברה").model_dump(),
                    ],
                ),
                (
                    BudgetEventCreate(
                        name="פסח", allocated_budget=17000, event_date=date(y, 4, 1),
                        status="הסתיים", notes="תווי קנייה",
                    ).model_dump(mode="json"),
                    [
                        ExpenseCreate(item_name="תווי קנייה", quantity=85, unit_price=200,
                                      status="שולם").model_dump(),
                    ],
                ),
                (
                    BudgetEventCreate(
                        name="יום גיבוש", allocated_budget=30000, event_date=date(y, 12, 28),
                        status="מתוכנן", notes="סדנה + ארוחת ערב",
                    ).model_dump(mode="json"),
                    [],
                ),
            ],
        ),
    ]


def _maternity(today: date) -> list[dict]:
    def d(days: int) -> date:
        return today + timedelta(days=days)

    records = [
        MaternityLeaveCreate(
            name="אורית שמעוני", phone="050-7001001", company_email="orit.s@example.com",
            birth_date=d(-20), baby_gender="בת", expected_return_date=d(85),
            gift_address="רחוב הרצל 12, רמת גן", delivery_contact_name="דוד שמעוני",
            delivery_contact_phone="052-7001002", notes="מעדיפה שליחות בשעות הבוקר",
        ),
        MaternityLeaveCreate(
            name="סיון אלמוג", phone="054-7002001", company_email="sivan.a@example.com",
            birth_date=d(-60), baby_gender="בן", expected_return_date=d(45),
            gift_address="שדרות בן גוריון 5, חיפה", attendance_updated=True,
        ),
        MaternityLeaveCreate(
            name="רותם נחום", phone="053-7003001", company_email="rotem.n@example.com",
            birth_date=d(-150), baby_gender="בת", expected_return_date=d(-45),
            attendance_updated=True, is_completed=True, notes="חזרה לעבודה במשרה מלאה",
        ),
        MaternityLeaveCreate(
            name="מאיה טל", phone="058-7004001", company_email="maya.t@example.com",
            expected_return_date=d(120), notes="לידה צפויה בחודש הבא",
        ),
    ]
    return [r.model_dump(mode="json") for r in records]


def tenant_is_demo(tenant_id: str, demo_tenant_id: str) -> bool:
    return check_owner_id(tenant_id) == check_owner_id(demo_tenant_id)


def seed_demo(db: FirestoreService, tenant_id: str, today: Optional[date] = None) -> dict[str, int]:
    """Fill an empty demo workspace. Returns what was created ({} if it already had data)."""
    check_owner_id(tenant_id)
    if db.tenant_has_data(tenant_id):
        logger.info("Demo workspace %s already has data — nothing seeded", tenant_id)
        return {}
    today = today or date.today()
    counts = {"jobs": 0, "candidates": 0, "talent_pool": 0, "annual_budgets": 0,
              "budget_events": 0, "expenses": 0, "maternity_leaves": 0}
    cvs = {p.key: load_demo_cv(p) for p in PEOPLE}

    for job_data, applications in JOBS:
        job = db.create_job(tenant_id, JobCreate(**job_data).model_dump())
        counts["jobs"] += 1
        for key, status, completed, referrer in applications:
            person = PEOPLE_BY_KEY[key]
            cv = cvs[key]
            record = {
                **person.record(),
                "recruitment_status": status,
                "is_completed": completed,
                "referred_by": referrer,
                "file_name": person.cv_file_name if cv else "",
            }
            db.create_candidate(tenant_id, job["id"], record, cv)
            counts["candidates"] += 1

    for key, referrer in POOL:
        person = PEOPLE_BY_KEY[key]
        cv = cvs[key]
        record = {**person.record(), "referred_by": referrer,
                  "file_name": person.cv_file_name if cv else ""}
        db.create_pool_candidate(tenant_id, record, cv)
        counts["talent_pool"] += 1

    for budget, events in _budgets(today):
        year = budget.pop("year")
        db.create_budget_year(tenant_id, year, budget)
        counts["annual_budgets"] += 1
        for event, expenses in events:
            saved = db.create_budget_event(tenant_id, year, event)
            counts["budget_events"] += 1
            for expense in expenses:
                db.create_event_expense(tenant_id, year, saved["id"], expense)
                counts["expenses"] += 1

    for record in _maternity(today):
        db.create_maternity_leave(tenant_id, record)
        counts["maternity_leaves"] += 1

    db.set_settings_doc(
        tenant_id,
        "maternity",
        MaternitySettings(notify_recipients=["hr@example.com"]).model_dump(),
    )
    logger.info("Demo workspace %s seeded: %s", tenant_id, counts)
    return counts


def reset_demo(db: FirestoreService, tenant_id: str, demo_tenant_id: str) -> dict:
    """Wipe the demo workspace and seed it again.

    Refuses (ValueError) unless ``tenant_id`` is the configured demo workspace, so a
    misconfiguration can never wipe a real workspace.
    """
    if not tenant_is_demo(tenant_id, demo_tenant_id):
        raise ValueError(f"Refusing to reset {tenant_id!r}: it is not the demo workspace")
    deleted = db.delete_tenant_data(tenant_id)
    created = seed_demo(db, tenant_id)
    return {"deleted": deleted, "created": created}
