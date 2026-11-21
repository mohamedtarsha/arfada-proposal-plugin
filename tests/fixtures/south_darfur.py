"""Synthetic South Darfur scenario (Final / end line evaluation of a food-voucher
project). Wording is written for the test, not copied from the client document,
but it keeps the features that broke Fast Mode in the first real run:

* the title says "Final Evaluation"; the body repeatedly says "end line evaluation";
* "baseline" appears many times, mostly as the existing comparison dataset;
* the proposal mixes current methodology counts (250 HH, 14 FGDs, 19 KIIs, census of
  40 CAC members) with breakdown tables and past-project statistics.
"""
from __future__ import annotations

TITLE = ("Terms of Reference: Final Evaluation of the Emergency Food Voucher Project "
         "in Nyala Shamal and Nyala Janoub, South Darfur")

_BODY = [
    ("background", "The project provided four rounds of paper vouchers to 1,300 households. "
     "A baseline survey was conducted in July 2026 with 243 households and the baseline "
     "report is available. Baseline values for FCS, rCSI and the hunger scale are listed "
     "in the indicator table."),
    ("objectives", "The purpose of this end line evaluation is to measure change against the "
     "baseline and to assess the contribution of the project. The consultant will conduct a "
     "final evaluation of the project and compare results with the baseline data."),
    ("scope", "The end line evaluation covers both localities. Endline values will be compared "
     "with baseline values using the same tools as the baseline questionnaire. The end line "
     "evaluation will reuse the baseline sample frame where lists are still valid."),
    ("required_methodology", "Mixed methods: a household survey of the original caseload, "
     "FGDs and KIIs. The baseline sample was 243 households. Findings from the end line "
     "evaluation must be disaggregated as in the baseline. Indicator: baseline FCS acceptable "
     "15.8%. Indicator: baseline rCSI. Baseline hunger scale categories apply."),
    ("deliverables", "Inception report, data collection, presentation of findings, end line "
     "evaluation draft report and final report."),
]

METADATA = {"assignment": {"value": TITLE}, "country": {"value": "Sudan"},
            "client": {"value": "ZOA"}}
for _k, _v in _BODY:
    METADATA[_k] = {"value": _v}

REQUIREMENTS = [
    {"req_id": "R1", "requirement_id": "R1", "text": "Assess progress against the baseline for all PMF indicators.",
     "category": "evaluation_questions"},
    {"req_id": "R2", "requirement_id": "R2", "text": "Sample size at 90% confidence and 5% margin of error; the "
     "baseline surveyed 243 households.", "category": "sampling"},
    {"req_id": "R3", "requirement_id": "R3", "text": "Qualitative assessment of the additional 2,000 households.",
     "category": "methodology"},
]

TOR = {"run_id": "tor_south_darfur", "metadata": METADATA,
       "assignment_type": {"assignment_type": "ENDLINE"}}

# Current-run decisions (provisional, Fast Mode)
REGISTER = {"decisions": [
    {"decision_id": "dec_sample_size", "question": "How many households will the survey cover?",
     "decision_status": "PROVISIONAL_RECOMMENDATION", "selected_value": 250, "minimum": 225,
     "category": "sampling", "source_text": "household survey sample"},
    {"decision_id": "dec_fgd_count", "question": "How many FGDs?",
     "decision_status": "PROVISIONAL_RECOMMENDATION", "selected_value": 14, "minimum": None,
     "category": "methodology", "source_text": "focus group discussions"},
    {"decision_id": "dec_kii_count", "question": "How many KIIs?",
     "decision_status": "PROVISIONAL_RECOMMENDATION", "selected_value": 19, "minimum": None,
     "category": "methodology", "source_text": "key informant interviews"},
]}

# ARFADA portfolio metrics (knowledge snapshot): historical, never current counts
SNAPSHOT_METRICS = {"total_projects": 156, "total_surveys": 73906, "total_kii": 2721,
                    "total_fgd": 1664, "countries": 9}


def _p(text):
    return {"type": "paragraph", "text": text}


SECTIONS = {
    "EXECUTIVE_SUMMARY": {"section_id": "EXECUTIVE_SUMMARY", "blocks": [
        _p("The design covers 250 household interviews from the original caseload, a census of "
           "all 40 CAC members, 14 FGDs, 19 KIIs and 20 short interviews with the additional "
           "caseload."),
    ]},
    "SAMPLING": {"section_id": "SAMPLING", "blocks": [
        _p("A finite population correction gives a minimum sample of 225 households; the "
           "baseline surveyed 243. We propose 250 completed household interviews, with a reserve "
           "list of 25 households (275 in total)."),
        {"type": "table", "columns": ["Parameter", "Value", "Note"], "rows": [
            ["Population (N)", "1,300 households", "Original caseload"],
            ["Minimum sample", "225", "With finite population correction"],
            ["Baseline sample", "243", "For comparability"],
            ["Proposed completed sample", "250", "FHH 150, MHH 100"],
        ]},
        {"type": "table", "columns": ["Method", "Group", "Nyala Shamal", "Nyala Janoub", "Total"],
         "rows": [
            ["FGD", "Women, original caseload", "1", "1", "2"],
            ["FGD", "Men, original caseload", "1", "1", "2"],
            ["FGD", "Youth (18-30)", "1", "1", "2"],
            ["FGD", "Marginalised groups", "1", "1", "2"],
            ["FGD", "CAC members", "1", "1", "2"],
            ["FGD", "Additional caseload", "2", "2", "4"],
            ["Census survey", "All CAC members", "20", "20", "40"],
            ["KII", "ZOA staff", "", "", "3"],
            ["KII", "HOPE staff", "", "", "3"],
            ["KII", "World Renew", "", "", "1"],
            ["KII", "Voucher vendors", "", "", "6"],
            ["KII", "Locality authorities", "", "", "2"],
            ["KII", "Community leaders", "", "", "2"],
            ["KII", "Other FSL actors", "", "", "2"],
        ]},
        _p("In total the plan covers 250 household interviews, 40 CAC members, 14 FGDs and "
           "19 KIIs. FGDs will have 8–10 participants. 4 FGDs with the additional caseload "
           "are reported separately."),
    ]},
    "EVALUATION_FRAMEWORK": {"section_id": "EVALUATION_FRAMEWORK", "blocks": [
        {"type": "table", "columns": ["Evaluation Question", "Method", "Respondent"], "rows": [
            ["EQ1 FCS, rCSI and hunger against targets", "Household survey", "Sampled households"],
            ["EQ4 CAC participation", "Census survey", "All 40 CAC members"],
            ["rCSI category", "0–3 category household survey", "Households"],
        ]},
    ]},
    "EXPERIENCE": {"section_id": "EXPERIENCE", "blocks": [
        _p("ARFADA's project tracker records 156 assignments, including 73,906 surveys, "
           "2,721 key informant interviews and 1,664 focus group discussions."),
        {"type": "table", "columns": ["Assignment", "Client / donor", "Country", "Year", "Scale"],
         "rows": [
            ["Final Evaluation, food and nutrition", "TGH", "Sudan", "2026",
             "197 surveys, 10 KIIs, 4 FGDs"],
            ["Final External Evaluation", "IRC / BHA", "Sudan", "2026",
             "580 surveys, 27 KIIs, 11 FGDs"],
            ["Endline Evaluation, joint response", "ZOA", "Syria", "2024",
             "766 surveys, 25 KIIs, 10 FGDs"],
        ]},
    ]},
    "TEAM": {"section_id": "TEAM", "blocks": [
        _p("The Team Leader has led evaluations with more than 400 surveys and 30 KIIs per "
           "assignment."),
    ]},
}
