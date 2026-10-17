"""Synthetic matching fixtures across industries, levels and awkward cases.

Every value here is invented for testing: no real candidate, employer, posting or salary appears in this
file. The point of the spread is that a matching rule which only works for software roles - or which
assumes a four-year degree, a specific country, or a strong experience signal - shows up as a failure
here rather than as a plausible-looking score in someone's window.

Each case pairs one profile with several listings and says which listing a person should *review first*:
the assertion is about the order and the reasons, never about a threshold being "good enough to apply".
"""
from __future__ import annotations

from dataclasses import dataclass

from career_agent.core import Availability, CandidateProfile, JobListing


@dataclass(frozen=True)
class MatchCase:
    """One industry's fixture: a profile, its listings, and which listing should come first."""

    domain: str
    note: str
    profile: CandidateProfile
    listings: tuple[JobListing, ...]
    expected_first: str


def listing(listing_id: str, *, employer: str = "Example Co", title: str = "Role", **overrides) -> JobListing:
    """A listing with the required fields filled in, so a case states only what it is about."""
    values = dict(
        listing_id=listing_id, source_id="manual", source_name="Manual entry",
        source_listing_url=f"https://jobs.example/{listing_id}", employer_name=employer,
        role_title=title, availability_status=Availability.OPEN,
        provenance_note="Synthetic fixture created for tests.",
    )
    values.update(overrides)
    return JobListing(**values)


#: Software and data: the shape most of the existing tests assume, kept here as one case among many.
SOFTWARE = MatchCase(
    domain="software/data",
    note="A student with Python and PostgreSQL against three data roles of differing fit.",
    profile=CandidateProfile(
        candidate_country="India", degree_discipline="Computer Science", study_status="undergraduate",
        graduation_year=2027, experience_years=0.5, work_authorization="authorized_without_sponsorship",
        skills=frozenset({"Python", "PostgreSQL", "SQL", "Git"}),
        preferred_locations=frozenset({"Bengaluru"}),
        preferred_work_modes=frozenset({"remote", "hybrid"}),
        preferred_role_types=frozenset({"internship"}),
    ),
    listings=(
        listing("sw-strong", employer="Data Shop", title="Data Engineering Intern",
                location_text="Bengaluru, India", work_mode="hybrid", role_type="internship",
                eligibility_scope="restricted", eligible_countries=("India",),
                allowed_degree_disciplines=("Computer Science",),
                allowed_study_statuses=("undergraduate",), allowed_graduation_years=(2027,),
                minimum_experience_years=0.0, maximum_experience_years=1.0,
                required_skills=frozenset({"Python", "SQL", "PostgreSQL"}),
                allowed_work_authorizations=("authorized_without_sponsorship",)),
        listing("sw-partial", employer="Platform Co", title="Platform Intern",
                location_text="Remote (India)", work_mode="remote", role_type="internship",
                eligibility_scope="restricted", eligible_countries=("India",),
                minimum_experience_years=0.0, maximum_experience_years=2.0,
                required_skills=frozenset({"Python", "Go", "Kubernetes", "Terraform"})),
        listing("sw-weak", employer="Enterprise", title="Senior Data Architect",
                location_text="Pune, India", work_mode="onsite", role_type="full_time",
                eligibility_scope="restricted", eligible_countries=("India",),
                minimum_experience_years=10.0, required_skills=frozenset({"Hadoop", "Spark", "Scala"})),
    ),
    expected_first="sw-strong",
)

#: Embedded and VLSI: different tools, and a degree requirement that is not computer science.
VLSI = MatchCase(
    domain="embedded/VLSI",
    note="A postgraduate with VHDL and verification experience against two hardware roles.",
    profile=CandidateProfile(
        candidate_country="India", degree_discipline="Electronics Engineering",
        study_status="postgraduate", graduation_year=2026, experience_years=2.0,
        work_authorization="authorized_without_sponsorship",
        skills=frozenset({"VHDL", "SystemVerilog", "Verification", "Python"}),
        preferred_locations=frozenset({"Hyderabad"}),
        preferred_work_modes=frozenset({"onsite", "hybrid"}),
        preferred_role_types=frozenset({"full_time"}),
    ),
    listings=(
        listing("vlsi-strong", employer="Silicon Co", title="Design Verification Engineer",
                location_text="Hyderabad, India", work_mode="hybrid", role_type="full_time",
                eligibility_scope="restricted", eligible_countries=("India",),
                allowed_degree_disciplines=("Electronics Engineering", "Electrical Engineering"),
                minimum_experience_years=1.0, maximum_experience_years=4.0,
                required_skills=frozenset({"SystemVerilog", "Verification"})),
        listing("vlsi-mismatch", employer="Foundry", title="Analog Layout Engineer",
                location_text="Hyderabad, India", work_mode="onsite", role_type="full_time",
                eligibility_scope="restricted", eligible_countries=("India",),
                allowed_degree_disciplines=("Electronics Engineering",),
                minimum_experience_years=1.0, maximum_experience_years=3.0,
                required_skills=frozenset({"Custom Layout", "Cadence", "DRC/LVS", "Analog Design"})),
    ),
    expected_first="vlsi-strong",
)

#: Mechanical engineering: an apprenticeship-style qualification, no software skills at all.
MECHANICAL = MatchCase(
    domain="mechanical",
    note="A diploma holder at the start of a career against a workshop role and a design role.",
    profile=CandidateProfile(
        candidate_country="India", degree_discipline="Mechanical Engineering",
        study_status="graduate", graduation_year=2025, experience_years=0.0,
        work_authorization="authorized_without_sponsorship",
        skills=frozenset({"AutoCAD", "SolidWorks", "GD&T", "Measurement"}),
        preferred_locations=frozenset({"Pune"}),
        preferred_work_modes=frozenset({"onsite"}),
        preferred_role_types=frozenset({"graduate_trainee", "full_time"}),
    ),
    listings=(
        listing("mech-strong", employer="Works Ltd", title="Graduate Trainee - Manufacturing",
                location_text="Pune, India", work_mode="onsite", role_type="graduate_trainee",
                eligibility_scope="restricted", eligible_countries=("India",),
                allowed_degree_disciplines=("Mechanical Engineering",),
                allowed_study_statuses=("graduate",),
                minimum_experience_years=0.0, maximum_experience_years=1.0,
                required_skills=frozenset({"AutoCAD", "GD&T"})),
        listing("mech-design", employer="Design House", title="Senior Mechanical Designer",
                location_text="Chennai, India", work_mode="onsite", role_type="full_time",
                eligibility_scope="restricted", eligible_countries=("India",),
                minimum_experience_years=6.0,
                required_skills=frozenset({"SolidWorks", "PTC Creo", "FEA", "Tolerance Analysis"})),
    ),
    expected_first="mech-strong",
)

#: Civil engineering: licensing language in the listing that the profile does not record.
CIVIL = MatchCase(
    domain="civil",
    note="A site engineer against two roles, one of which asks for a licence the profile omits.",
    profile=CandidateProfile(
        candidate_country="India", degree_discipline="Civil Engineering", study_status="graduate",
        graduation_year=2024, experience_years=3.0, skills=frozenset({"AutoCAD", "Estimation", "RCC"}),
        preferred_locations=frozenset({"Mumbai"}),
        preferred_work_modes=frozenset({"onsite"}),
        preferred_role_types=frozenset({"full_time"}),
    ),
    listings=(
        listing("civil-strong", employer="Builders", title="Site Engineer",
                location_text="Mumbai, India", work_mode="onsite", role_type="full_time",
                eligibility_scope="restricted", eligible_countries=("India",),
                allowed_degree_disciplines=("Civil Engineering",),
                minimum_experience_years=2.0, maximum_experience_years=6.0,
                required_skills=frozenset({"AutoCAD", "RCC", "Estimation"})),
        listing("civil-licensed", employer="Infra Corp", title="Structural Engineer (Licensed)",
                location_text="Mumbai, India", work_mode="onsite", role_type="full_time",
                eligibility_scope="restricted", eligible_countries=("India",),
                minimum_experience_years=4.0,
                required_skills=frozenset({"STAAD Pro", "Structural Design"})),
    ),
    expected_first="civil-strong",
)

#: Design: a portfolio-oriented profile where the listing states no degree at all.
DESIGN = MatchCase(
    domain="design",
    note="A self-taught designer: the listing's silence about degrees must not be scored as a pass.",
    profile=CandidateProfile(
        candidate_country="India", skills=frozenset({"Figma", "Typography", "User Research"}),
        preferred_work_modes=frozenset({"remote"}), preferred_role_types=frozenset({"contract"}),
    ),
    listings=(
        listing("design-remote", employer="Studio", title="Product Designer (Contract)",
                location_text="Remote", work_mode="remote", role_type="contract",
                required_skills=frozenset({"Figma", "Typography", "User Research"})),
        listing("design-onsite", employer="Agency", title="Brand Designer",
                location_text="Delhi, India", work_mode="onsite", role_type="full_time",
                required_skills=frozenset({"Illustrator", "After Effects"})),
    ),
    expected_first="design-remote",
)

#: Business: a profile with almost nothing recorded, which must produce "not enough information".
SPARSE = MatchCase(
    domain="business (sparse record)",
    note="A profile with no skills, no preferences and no location: nothing may be invented for it.",
    profile=CandidateProfile(candidate_country="India"),
    listings=(
        listing("biz-thin", employer="Consultancy", title="Business Analyst",
                location_text="Gurugram, India", work_mode="hybrid", role_type="full_time",
                required_skills=frozenset({"Excel", "SQL", "Stakeholder Management"})),
    ),
    expected_first="biz-thin",
)

#: A listing that asks for skills, experience, a degree and a location, against a person who has
#: recorded only skills: one factor out of ten weight units is comparable, so the reading must not be
#: confident however perfectly that one factor matches.
SKILLS_ONLY = MatchCase(
    domain="one known factor of many",
    note="A perfect skills match with nothing else recorded is a small sample, not a strong fit.",
    profile=CandidateProfile(candidate_country="India", skills=frozenset({"Python", "SQL", "Docker"})),
    listings=(
        listing("one-factor", employer="Systems Co", title="Backend Engineer",
                location_text="Pune, India", work_mode="onsite", role_type="full_time",
                allowed_degree_disciplines=("Computer Science",),
                minimum_experience_years=2.0, maximum_experience_years=5.0,
                required_skills=frozenset({"Python", "SQL", "Docker"})),
    ),
    expected_first="one-factor",
)

#: A listing that states almost nothing: the assessment must say so rather than score it well.
SILENT_LISTING = MatchCase(
    domain="listing with no requirements stated",
    note="A posting with no skills, no experience range and no location: no factor may be guessed.",
    profile=CandidateProfile(
        candidate_country="India", degree_discipline="Computer Science", study_status="graduate",
        graduation_year=2026, experience_years=1.0, skills=frozenset({"Python"}),
        preferred_locations=frozenset({"Remote"}), preferred_work_modes=frozenset({"remote"}),
        preferred_role_types=frozenset({"full_time"}),
    ),
    listings=(
        listing("silent-role", employer="Quiet Co", title="Graduate Engineer"),
    ),
    expected_first="silent-role",
)

ALL_CASES = (SOFTWARE, VLSI, MECHANICAL, CIVIL, DESIGN, SPARSE, SILENT_LISTING, SKILLS_ONLY)


def case_by_domain(domain: str) -> MatchCase:
    """One fixture by its domain name, so a test failure names the industry it broke for."""
    for case in ALL_CASES:
        if case.domain == domain:
            return case
    raise KeyError(f"No matching fixture for {domain!r}; known: {[c.domain for c in ALL_CASES]}")
