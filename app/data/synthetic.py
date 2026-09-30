"""Fictional customers and mock peer cohorts.

Nothing here is a KBC customer, a quote, or a market rate.
"""

from datetime import date

from app.simulation.models import CustomerProfile, PeerCohort

# Fixed clock so goal dates do not drift between runs.
AS_OF = date(2026, 9, 30)

# Mock consumer-loan rate for the demo. Not a KBC quote.
MOCK_CAR_APR = 0.059

HORIZON_MONTHS = 36
GOAL_SEARCH_MONTHS = 360

ALEX = CustomerProfile(
    id="alex",
    name="Alex",
    monthly_net_income=3200,
    savings=18500,
    monthly_housing=900,
    monthly_fixed_other=550,
    monthly_variable=850,
    emergency_months_goal=6,
    apartment_goal=40000,
)

SAM = CustomerProfile(
    id="sam",
    name="Sam",
    monthly_net_income=4100,
    savings=6200,
    monthly_housing=1100,
    monthly_fixed_other=700,
    monthly_variable=1400,
    emergency_months_goal=3,
    apartment_goal=25000,
)

PROFILES = {
    ALEX.id: ALEX,
    SAM.id: SAM,
}

# Aggregated stand-ins for "financially similar" profiles. Invented for the demo.
ALEX_COHORT = PeerCohort(
    label="Similar Financial Profiles",
    income_band="€3,000–€3,500 per month",
    fixed_cost_ratio=0.42,
    savings_rate=0.22,
    runway_after_similar_purchase_months=4.8,
    traits=(
        "Income €3,000–€3,500 net",
        "Fixed costs around 42% of income",
        "Typical savings rate around 22%",
        "Housing, fixed bills, and variable spending in a similar mix",
    ),
)

SAM_COHORT = PeerCohort(
    label="Similar Financial Profiles",
    income_band="€3,800–€4,400 per month",
    fixed_cost_ratio=0.44,
    savings_rate=0.20,
    runway_after_similar_purchase_months=2.1,
    traits=(
        "Income €3,800–€4,400 net",
        "Fixed costs around 44% of income",
        "Typical savings rate around 20%",
        "A thinner cash buffer than Alex's cohort",
    ),
)

COHORTS = {
    ALEX.id: ALEX_COHORT,
    SAM.id: SAM_COHORT,
}
