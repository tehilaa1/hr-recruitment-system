from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.models.candidate import DEFAULT_STATUS
from app.services.cv_file_service import cv_info
from app.services.dedup_service import normalize_email, normalize_phone

_MIN_PHONE_QUERY_DIGITS = 3
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)

# Internal marker on talent-pool records while grouping (never returned)
_POOL = "_from_talent_pool"


def search_candidates(
    query: str,
    candidates: list[dict],
    jobs_by_id: dict[str, dict],
    limit: int = 20,
    pool_candidates: list[dict] | None = None,
) -> list[dict]:
    """Search candidates across all jobs and the talent pool; return merged person profiles.

    Records sharing an email or phone are merged into one person, so a match on
    any of a person's records returns their full application history plus
    their talent-pool entries (if any).
    """
    query = (query or "").strip()
    if not query:
        return []
    groups = _people(candidates, pool_candidates)
    matched = [g for g in groups if any(_matches(query, c) for c in g)]
    return _profiles(matched, jobs_by_id)[:limit]


def list_people(
    candidates: list[dict],
    jobs_by_id: dict[str, dict],
    pool_candidates: list[dict] | None = None,
) -> list[dict]:
    """Every person (job applications + talent pool, merged by email/phone), most recently active first."""
    return _profiles(_people(candidates, pool_candidates), jobs_by_id)


def find_person(
    record_id: str,
    candidates: list[dict],
    jobs_by_id: dict[str, dict],
    pool_candidates: list[dict] | None = None,
) -> dict | None:
    """The profile of the person that one record (application or pool entry) belongs to."""
    group = next(
        (g for g in _people(candidates, pool_candidates) if any(r.get("id") == record_id for r in g)),
        None,
    )
    return _profiles([group], jobs_by_id)[0] if group else None


def list_referrers(records: list[dict]) -> list[str]:
    """Distinct referrer names across applications and pool entries, most used first.

    Names differing only in case/spacing count as one (the most common spelling wins).
    """
    spellings: dict[str, Counter] = {}
    for r in records:
        name = re.sub(r"\s+", " ", str(r.get("referred_by") or "")).strip()
        if name:
            spellings.setdefault(name.casefold(), Counter())[name] += 1
    ranked = sorted(spellings.values(), key=lambda c: (-sum(c.values()), c.most_common(1)[0][0]))
    return [c.most_common(1)[0][0] for c in ranked]


def _people(candidates: list[dict], pool_candidates: list[dict] | None) -> list[list[dict]]:
    records = list(candidates) + [{**c, _POOL: True} for c in pool_candidates or []]
    return _group_by_identity(records)


def _profiles(groups: list[list[dict]], jobs_by_id: dict[str, dict]) -> list[dict]:
    profiles = [_build_profile(g, jobs_by_id) for g in groups]
    profiles.sort(key=lambda p: p.pop("_latest"), reverse=True)
    return profiles


# ------------------------------------------------------------------ #
# Matching                                                             #
# ------------------------------------------------------------------ #


def _norm_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _matches(query: str, candidate: dict) -> bool:
    q = _norm_text(query)

    first = _norm_text(candidate.get("full_name"))
    last = _norm_text(candidate.get("family_name"))
    names = (first, last, f"{first} {last}".strip(), f"{last} {first}".strip())
    if any(q in n for n in names if n):
        return True

    email = normalize_email(candidate.get("email"))
    if email and q in email:
        return True

    if _is_phone_query(query):
        stored = _local_digits(candidate.get("phone"))
        if stored and _local_digits(query) in stored:
            return True

    return False


def _local_digits(value: Any) -> str:
    """Digits only, with an Israeli +972 / 00972 prefix turned into a leading 0.

    Unlike normalize_phone this has no minimum length, so partial queries work.
    """
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("00972"):
        return "0" + digits[5:]
    if digits.startswith("972"):
        return "0" + digits[3:]
    return digits


def _is_phone_query(query: str) -> bool:
    """Digits plus phone punctuation only (no letters), with enough digits to be useful."""
    return bool(re.fullmatch(r"[\d\s+\-()]+", query)) and (
        len(re.sub(r"\D", "", query)) >= _MIN_PHONE_QUERY_DIGITS
    )


# ------------------------------------------------------------------ #
# Grouping records into people                                        #
# ------------------------------------------------------------------ #


def _group_by_identity(candidates: list[dict]) -> list[list[dict]]:
    """Union-find over records: same normalized email or phone => same person."""
    parent = list(range(len(candidates)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    first_seen: dict[str, int] = {}
    for idx, c in enumerate(candidates):
        for key in (
            f"e:{normalize_email(c.get('email'))}" if c.get("email") else None,
            f"p:{normalize_phone(c.get('phone'))}" if normalize_phone(c.get("phone")) else None,
        ):
            if key is None:
                continue
            if key in first_seen:
                union(first_seen[key], idx)
            else:
                first_seen[key] = idx

    grouped: dict[int, list[dict]] = {}
    for idx, c in enumerate(candidates):
        grouped.setdefault(find(idx), []).append(c)
    return list(grouped.values())


def _created(c: dict) -> datetime:
    value = c.get("created_at")
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _EPOCH


def _unique(values, key=lambda v: v.lower()) -> list[str]:
    seen, out = set(), []
    for v in values:
        v = str(v or "").strip()
        k = key(v) if v else ""
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


def _build_profile(records: list[dict], jobs_by_id: dict[str, dict]) -> dict:
    records = sorted(records, key=_created, reverse=True)

    def latest(field: str):
        # Most recent non-empty value for a field
        return next((r.get(field) for r in records if r.get(field)), None)

    years = latest("years_of_experience")
    try:
        years = int(years or 0)
    except (TypeError, ValueError):
        years = 0

    applications = []
    pool_entries = []
    for r in records:
        if r.get(_POOL):
            pool_entries.append(
                {
                    "pool_id": r["id"],
                    "file_name": r.get("file_name") or "",
                    "cv_file": cv_info(r),
                    "referred_by": _referrer(r),
                    "created_at": r.get("created_at") if isinstance(r.get("created_at"), datetime) else None,
                }
            )
            continue
        job = jobs_by_id.get(r.get("job_id") or "")
        job_exists = job is not None
        job = job or {}
        applications.append(
            {
                "candidate_id": r["id"],
                "job_id": r.get("job_id") or "",
                "job_title": job.get("job_title") or ("ללא כותרת" if job_exists else "משרה שנמחקה"),
                "job_exists": job_exists,
                "interview_type": job.get("interview_type"),
                "interview_location": job.get("interview_location") or "",
                "recruitment_status": r.get("recruitment_status") or DEFAULT_STATUS,
                "is_completed": bool(r.get("is_completed")),
                "referred_by": _referrer(r),
                "file_name": r.get("file_name") or "",
                "cv_file": cv_info(r),
                "created_at": r.get("created_at") if isinstance(r.get("created_at"), datetime) else None,
            }
        )

    return {
        # Stable key for the UI: the oldest record's id
        "key": records[-1]["id"],
        "full_name": str(latest("full_name") or ""),
        "family_name": str(latest("family_name") or ""),
        "emails": _unique(r.get("email") for r in records),
        "phones": _unique((r.get("phone") for r in records), key=_local_digits),
        "address": str(latest("address") or ""),
        "profession": str(latest("profession") or ""),
        "years_of_experience": years,
        "applications": applications,
        "in_talent_pool": bool(pool_entries),
        "talent_pool_entries": pool_entries,
        "referrers": _unique(_referrer(r) for r in records),
        "last_activity": _created(records[0]) if _created(records[0]) != _EPOCH else None,
        # Sort key for search results (popped before returning)
        "_latest": _created(records[0]),
    }


def _referrer(record: dict) -> str:
    return re.sub(r"\s+", " ", str(record.get("referred_by") or "")).strip()
