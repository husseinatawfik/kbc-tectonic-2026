"""Turn a customer and a set of decisions into two parallel futures."""

from datetime import date

from app.simulation.decisions import BuiltDecision, decisions_from_payload, future_label
from app.simulation.engine import project_path
from app.simulation.explain import assumption_note, format_date, peer_statements, percent, tradeoff_statements
from app.simulation.models import CustomerProfile, PathProjection, PeerCohort


def simulate_parallel(
    profile: CustomerProfile,
    cohort: PeerCohort,
    *,
    as_of: date,
    decisions: list[BuiltDecision],
    annual_interest_rate: float,
    horizon_months: int,
    search_months: int,
) -> dict:
    built = tuple(decisions)
    adjustments = tuple(adjustment for item in built for adjustment in item.adjustments)
    views = tuple(item.view for item in built)
    label = future_label(list(built))
    current = project_path(
        profile,
        "current",
        "Current Path",
        None,
        as_of=as_of,
        horizon_months=horizon_months,
        search_months=search_months,
    )
    future = project_path(
        profile,
        "future",
        label,
        adjustments,
        as_of=as_of,
        horizon_months=horizon_months,
        search_months=search_months,
        decisions=views,
    )
    rate_label = f"{annual_interest_rate:.1%} APR"
    return {
        "as_of": as_of.isoformat(),
        "horizon_months": horizon_months,
        "customer": _customer_payload(profile),
        "assumptions": {
            "annual_interest_rate": annual_interest_rate,
            "annual_interest_rate_label": rate_label,
            "note": assumption_note(rate_label=rate_label, decisions=views),
        },
        "scenarios": [_scenario_payload(current, profile), _scenario_payload(future, profile)],
        "comparison": {
            "statements": tradeoff_statements(profile, current, future, views),
        },
        "peers": {
            "label": cohort.label,
            "disclaimer": "Synthetic demo data. These figures are not drawn from real KBC customers.",
            "traits": list(cohort.traits),
            "statements": peer_statements(profile, future, cohort, views),
        },
    }


def simulate_from_payload(
    profile: CustomerProfile,
    cohort: PeerCohort,
    payload: dict,
    *,
    as_of: date,
    annual_interest_rate: float,
    horizon_months: int,
    search_months: int,
) -> dict:
    decisions = decisions_from_payload(profile, payload, annual_interest_rate=annual_interest_rate)
    return simulate_parallel(
        profile,
        cohort,
        as_of=as_of,
        decisions=decisions,
        annual_interest_rate=annual_interest_rate,
        horizon_months=horizon_months,
        search_months=search_months,
    )


def _customer_payload(profile: CustomerProfile) -> dict:
    expenses = round(profile.monthly_expenses, 2)
    return {
        "id": profile.id,
        "name": profile.name,
        "savings": round(profile.savings, 2),
        "monthly_net_income": round(profile.monthly_net_income, 2),
        "monthly_housing": round(profile.monthly_housing, 2),
        "monthly_fixed_other": round(profile.monthly_fixed_other, 2),
        "monthly_variable": round(profile.monthly_variable, 2),
        "monthly_expenses": expenses,
        "monthly_disposable_income": round(profile.monthly_disposable_income, 2),
        "emergency_runway_months": round(profile.savings / expenses, 2) if expenses else 0,
        "emergency_months_goal": profile.emergency_months_goal,
        "apartment_goal": round(profile.apartment_goal, 2),
        "apartment_progress": round(profile.savings / profile.apartment_goal, 4),
        "fixed_cost_ratio": round(profile.fixed_cost_ratio, 4),
        "savings_rate": round(profile.savings_rate, 4),
    }


def _scenario_payload(path: PathProjection, profile: CustomerProfile) -> dict:
    year_one = path.point(min(12, len(path.points) - 1))
    year_three = path.point(len(path.points) - 1)
    after_decision = path.point(1)
    horizon_points = [point for point in path.points if point.month >= 1]
    lowest = min(horizon_points, key=lambda point: point.savings)
    return {
        "id": path.scenario_id,
        "label": path.label,
        "monthly_disposable_income": path.monthly_disposable_income,
        "savings_after_1_year": year_one.savings,
        "savings_after_3_years": year_three.savings,
        "emergency_runway_after_decision": after_decision.emergency_runway_months,
        "emergency_runway_after_3_years": year_three.emergency_runway_months,
        "savings_rate_month_one": None
        if after_decision.savings_rate is None
        else round(after_decision.savings_rate, 4),
        "savings_rate_month_one_label": percent(after_decision.savings_rate),
        "lowest_savings": lowest.savings,
        "lowest_savings_month": lowest.month,
        "months_to_apartment_goal": path.months_to_apartment_goal,
        "apartment_goal_date": None
        if path.apartment_goal_date is None
        else path.apartment_goal_date.isoformat(),
        "apartment_goal_label": format_date(path.apartment_goal_date) or "Not reached within 30 years",
        "decisions": [
            {"id": item.id, "label": item.label, "detail": item.detail}
            for item in path.decisions
        ],
        "series": [
            {
                "month": point.month,
                "savings": point.savings,
                "monthly_income": point.monthly_income,
                "monthly_disposable_income": point.monthly_disposable_income,
                "monthly_expenses": point.monthly_expenses,
                "emergency_runway_months": point.emergency_runway_months,
                "loan_payment": point.loan_payment,
                "savings_rate": None if point.savings_rate is None else round(point.savings_rate, 4),
            }
            for point in path.points
        ],
        "emergency_months_goal": profile.emergency_months_goal,
    }
