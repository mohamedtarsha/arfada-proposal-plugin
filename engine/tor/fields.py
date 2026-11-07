"""PE2 TOR field taxonomy + deterministic heading/keyword signals.

FIELDS is the ordered 22-field schema the user specified. Each field maps to a set
of heading aliases (matched against PE1 section headings) and inline keyword cues
(matched against block text as a fallback for PDF TORs with weak section trees).
Nothing here does extraction — it's the controlled vocabulary the extractor uses.
"""
from __future__ import annotations

# Ordered canonical field keys (== the user's list)
FIELDS = [
    "assignment", "client", "country", "background", "objectives", "scope",
    "locations", "target_groups", "required_methodology", "sampling_requirements",
    "data_collection_methods", "deliverables", "timeline", "team_requirements",
    "evaluation_questions", "proposal_requirements", "scoring_criteria",
    "page_limits", "submission_requirements", "annexes", "ethics_safeguarding",
    "research_needs",
]

FIELD_LABEL = {
    "assignment": "Assignment", "client": "Client", "country": "Country",
    "background": "Background", "objectives": "Objectives", "scope": "Scope",
    "locations": "Locations", "target_groups": "Target Groups",
    "required_methodology": "Required Methodology",
    "sampling_requirements": "Sampling Requirements",
    "data_collection_methods": "Data Collection Methods", "deliverables": "Deliverables",
    "timeline": "Timeline", "team_requirements": "Team Requirements",
    "evaluation_questions": "Evaluation Questions",
    "proposal_requirements": "Proposal Requirements", "scoring_criteria": "Scoring Criteria",
    "page_limits": "Page Limits", "submission_requirements": "Submission Requirements",
    "annexes": "Annexes", "ethics_safeguarding": "Ethics / Safeguarding",
    "research_needs": "Research Needs",
}

# Heading aliases (lowercased substrings). Order matters: earlier fields claim a
# heading first, so specific headings (e.g. "sampling") beat generic ("methodology").
HEADING_ALIASES: dict[str, list[str]] = {
    "background": ["background", "context", "introduction", "about the project",
                   "project description", "situation analysis"],
    "objectives": ["objective", "purpose of the", "purpose", "aim", "goal",
                   "rationale"],
    "evaluation_questions": ["evaluation question", "key question", "learning question",
                             "research question", "key evaluation question"],
    "scope": ["scope of work", "scope of the assignment", "scope", "assignment scope"],
    "locations": ["geographic", "geographical", "target area", "target location",
                  "area of coverage", "location of the assignment", "coverage area"],
    "target_groups": ["target group", "target population", "target respondent",
                      "beneficiaries", "participants", "respondent", "population of interest"],
    "sampling_requirements": ["sampling", "sample size", "sample and instrument",
                              "sample"],
    "data_collection_methods": ["data collection", "primary data", "methods of data",
                                "data collection tools", "collection methods"],
    "required_methodology": ["methodology", "evaluation approach", "evaluation design",
                             "research design", "approach and method", "proposed approach",
                             "methodological"],
    "deliverables": ["deliverable", "expected output", "expected deliverable", "outputs",
                     "key deliverable", "products"],
    "timeline": ["timeline", "duration", "time frame", "timeframe", "work plan",
                 "workplan", "schedule", "period of performance", "assignment duration"],
    "team_requirements": ["team composition", "key personnel", "personnel", "qualification",
                          "required expertise", "expertise", "consultant profile",
                          "team requirement", "staffing", "roles and", "responsibilities",
                          "experience required", "evaluator profile"],
    "proposal_requirements": ["technical proposal", "proposal structure", "content of the proposal",
                              "proposal requirement", "required sections", "proposal format",
                              "structure of the proposal", "expression of interest", "proposal should"],
    "scoring_criteria": ["evaluation criteria", "selection criteria", "assessment criteria",
                         "scoring", "technical evaluation", "evaluation of proposals",
                         "award criteria", "criteria for evaluation"],
    "page_limits": ["page limit", "page limitation", "length of the proposal", "maximum length"],
    "submission_requirements": ["submission", "how to apply", "application process",
                                "deadline", "closing date", "submit", "instructions to"],
    "annexes": ["annex", "appendix", "attachment", "enclosure"],
    "ethics_safeguarding": ["ethic", "safeguard", "psea", "child protection", "do no harm",
                            "data protection", "gdpr", "confidentiality and", "protection from"],
    "research_needs": ["research need", "evidence gap", "literature review", "desk review",
                       "secondary data", "background research"],
}

# Inline keyword cues for block-scan fallback (esp. PDF TORs with weak section
# trees). Broad enough to give partial coverage, LOW confidence.
KEYWORD_CUES: dict[str, list[str]] = {
    "background": ["background", "context", "the project aims", "funded by", "implemented by"],
    "objectives": ["objective of", "purpose of", "the evaluation aims", "the assignment aims",
                   "overall objective", "specific objective"],
    "scope": ["scope of work", "scope of the", "the consultant will", "the evaluation will assess"],
    "deliverables": ["deliverable", "inception report", "final report", "shall submit",
                     "will produce", "expected outputs"],
    "team_requirements": ["team leader", "evaluator", "qualification", "years of experience",
                          "key personnel", "expertise in", "consultant profile"],
    "required_methodology": ["methodology", "mixed method", "the evaluation will use",
                             "data collection and analysis", "approach"],
    "page_limits": ["page limit", "not exceed", "maximum of", "no more than", "pages maximum"],
    "timeline": ["weeks", "months", "working days", "duration of", "shall be completed"],
    "submission_requirements": ["deadline", "submitted by", "closing date", "submission of",
                                "expression of interest", "proposals must be"],
    "sampling_requirements": ["sample size", "sampling", "confidence level", "margin of error"],
    "data_collection_methods": ["kii", "fgd", "focus group", "key informant", "survey",
                                "questionnaire", "in-depth interview", "observation"],
    "ethics_safeguarding": ["psea", "safeguarding", "informed consent", "do no harm",
                            "child protection", "ethical approval"],
    "evaluation_questions": ["evaluation questions", "the evaluation will answer",
                             "key questions", "relevance", "effectiveness", "efficiency",
                             "sustainability", "impact"],
    "scoring_criteria": ["technical score", "financial score", "weighting", "points awarded",
                         "evaluation criteria", "scoring", "weighted"],
    "annexes": ["annex", "appendix", "attachment"],
    "target_groups": ["target group", "beneficiaries", "respondents", "participants"],
    "locations": ["governorate", "district", "target location", "geographic"],
}

# Fields whose section content should be segmented into atomic REQUIREMENTS.
REQUIREMENT_SOURCE_FIELDS = [
    "deliverables", "proposal_requirements", "scope", "required_methodology",
    "team_requirements", "submission_requirements", "data_collection_methods",
    "ethics_safeguarding",
]

# category per source field (for the requirement list)
REQUIREMENT_CATEGORY = {
    "deliverables": "deliverable", "proposal_requirements": "proposal_format",
    "scope": "scope", "required_methodology": "methodology",
    "team_requirements": "team", "submission_requirements": "submission",
    "data_collection_methods": "methodology", "ethics_safeguarding": "ethics",
}

# Heading contexts whose list items describe the PROJECT/context, not consultant
# obligations. Items here are harvested ONLY if they carry an explicit actor-obligation
# cue (below) — this stops project-activity bullets inflating the requirement set.
NON_REQ_HEADINGS = ("background", "context", "introduction", "about the", "project description",
                    "project background", "situation analysis", "project summary", "activities",
                    "activity information", "sector outcome", "expected sector outcome",
                    "expected outcome", "geographic area", "targeted geographic", "target area",
                    "project goal", "goal and objective", "thematic area", "project overview")
ACTOR_OBLIGATION_CUES = ("shall", "must", "the consultant", "consultant will", "consultant is",
                         "the bidder", "bidder", "tenderer", "the evaluator", "evaluator will",
                         "the firm", "the contractor", "contractor shall", "contractor will",
                         "proposal must", "is required", "are required", "expected to")

MANDATORY_CUES = ("shall", "must", "required", "mandatory", "is required", "are required",
                  "will be required", "expected to", "should include", "at a minimum",
                  "minimum requirement", "no later than", "at least", "responsible for",
                  "will be signed", "bound to", "obliged", "minimum of", "will comprise")
OPTIONAL_CUES = ("should", "may ", "encouraged", "preferred", "desirable", "optional",
                 "where possible", "if applicable", "nice to have", "ideally", "can include")

# STRONG optional signals: in TOR-speak requirements are mandatory BY DEFAULT; only these
# clearly soften an obligation. Bare "should" is usually mandatory ("should not exceed"),
# so it is NOT here — only "should consider/explore/ideally" (handled in _modality).
STRONG_OPTIONAL_CUES = ("may ", "preferred", "desirable", "optional", "encouraged", "ideally",
                        "nice to have", "an asset", "advantage", "where possible", "if applicable",
                        "is a plus", "would be an asset", "not mandatory", "not required")
EXPLICIT_MANDATORY = ("shall", "must", "mandatory", "is required", "are required", "will be required",
                      "no later than", "at a minimum", "obliged", "bound to")

# Future-prescriptive phrases: in a TOR, "the study will use X" prescribes a method and
# is a requirement (even though modality stays UNSPECIFIED unless a modal is present).
PRESCRIPTIVE_CUES = ("will use", "will employ", "will utilize", "will utilise", "will apply",
                     "will adopt", "will be used", "will be administered", "will be trained",
                     "will be sought", "will adhere", "will cover", "will target",
                     "will be prepared", "will be conducted", "will be collected", "will follow",
                     "will comprise", "will be disaggregated", "will be translated")

# Obligation verbs that (typically sentence-initial) mark an imperative requirement even
# without a modal — critical for PDF/narrative TORs with no list structure.
OBLIGATION_VERBS = ("submit", "provide", "deliver", "conduct", "ensure", "develop", "prepare",
                    "present", "review", "analyse", "analyze", "produce", "undertake",
                    "carry out", "collect", "design", "facilitate", "translate", "obtain",
                    "map", "assess", "generate", "profile", "test", "validate", "sign")

# Ordered content-based category classifier (first hit wins). Used when there is no
# usable section heading (PDF / head-less DOCX) or the heading is generic.
CATEGORY_CONTENT_CUES = [
    ("ethics", ("consent", "safeguard", "psea", "do no harm", "do-no-harm", "confidential",
                "ethical", "child protection", "gbv", "risk assessment", "code of conduct",
                "data protection", "privacy")),
    ("team", ("team leader", "evaluator", "years of experience", "qualification", "master",
              "bachelor", "degree", "expertise", "consultant profile", "personnel", "expert",
              "cv ", "curriculum vitae", "years of", "proven experience", "proven record",
              "access permit", "staffing", "demonstrated ability", "strong understanding",
              "knowledge of", "familiarity", "track record", "experience in", "ability to",
              "skills", "competenc", "fluency", "fluent in")),
    ("sampling", ("sample size", "sampling", "confidence level", "margin of error", "stratified",
                  "cluster", "disaggregat", "representative sample", "respondents will",
                  "sample of")),
    ("deliverable", ("inception report", "final report", "draft report", "deliverable", "dataset",
                     "presentation", "workshop", "final assessment report", "outputs", "work plan",
                     "workplan", "power point", "powerpoint")),
    ("data_collection_methods", ("kii", "fgd", "idi", "in-depth interview", "questionnaire",
                                 "household survey", "survey", "observation", "focus group",
                                 "key informant", "primary data", "secondary data")),
    ("evaluation_questions", ("relevance", "effectiveness", "efficiency", "sustainability",
                              "evaluation question", "key question", "lines of inquiry")),
    ("submission", ("deadline", "closing date", "page", "font", "proposal must", "submitted by",
                    "cover letter", "annex", "email", "portal", "financial proposal",
                    "technical proposal", "lumpsum", "lump sum", "validity", "template")),
    ("timeline", ("working days", "calendar days", "no later than", "by end of", "duration of",
                  "week", "month", "milestone", "deadline")),
    ("methodology", ("methodology", "mixed method", "mixed-method", "desk review", "triangulation",
                     "qualitative", "quantitative", "data collection", "approach", "participatory",
                     "field visit", "remote", "logframe", "logical framework", "theory of change")),
    ("scope", ("scope", "objective", "assess", "evaluate", "indicator", "review the")),
]
