"""Neutral descriptions of a projection.

These sentences report differences. They do not tell the customer what to do.
"""

from app.simulation.models import CustomerProfile, DecisionView, MonthPoint, PathProjection, PeerCohort


def euro(amount: float) -> str:
    sign = "-" if amount < 0 else ""
    cents = int(round(abs(amount) * 100))
    whole, remainder = divmod(cents, 100)
    body = f"{whole:,}"
    if remainder:
        return f"{sign}€{body}.{remainder:02d}"
    return f"{sign}€{body}"


def format_date(value) -> str | None:
    if value is None:
        return None
    return f"{value.day} {value.strftime('%B %Y')}"


def percent(rate: float | None) -> str:
    if rate is None:
        return "not defined"
    return f"{rate:.0%}"


def tradeoff_statements(
    profile: CustomerProfile,
    current: PathProjection,
    alternative: PathProjection,
    decisions: tuple[DecisionView, ...],
) -> list[str]:
    if not decisions:
        return [
            "No decision is applied, so this future matches the current path on savings, "
            "disposable income, and the apartment date."
        ]

    statements: list[str] = []
    current_months = current.months_to_apartment_goal
    other_months = alternative.months_to_apartment_goal
    goal = euro(profile.apartment_goal)

    if current_months is not None and other_months is not None:
        delay = other_months - current_months
        if delay > 0:
            statements.append(f"This future delays the {goal} apartment deposit by approximately {delay} months.")
        elif delay < 0:
            statements.append(
                f"This future brings the {goal} apartment deposit forward by approximately {-delay} months."
            )
        else:
            statements.append("This future reaches the apartment deposit on the same schedule as the current path.")
    elif other_months is None and current_months is not None:
        statements.append(
            f"Within 30 years, this future does not reach the {goal} apartment deposit. "
            f"The current path reaches it in {current_months} months."
        )
    elif other_months is not None and current_months is None:
        statements.append(
            "This future reaches the apartment deposit within 30 years. The current path does not."
        )
    else:
        statements.append("Neither path reaches the apartment deposit within 30 years.")

    horizon = min(len(current.points), len(alternative.points)) - 1
    year_one = min(12, horizon)
    statements.append(
        f"After 1 year, projected savings are {euro(alternative.point(year_one).savings)} "
        f"on this future and {euro(current.point(year_one).savings)} on the current path."
    )
    statements.append(
        f"After 3 years, projected savings are {euro(alternative.point(horizon).savings)} "
        f"on this future and {euro(current.point(horizon).savings)} on the current path."
    )
    statements.append(
        f"In month 1, disposable income is {euro(alternative.point(1).monthly_disposable_income)} "
        f"on this future and {euro(current.point(1).monthly_disposable_income)} on the current path."
    )
    statements.append(
        "One month in, emergency runway is "
        f"{alternative.point(1).emergency_runway_months:.1f} months on this future, compared with "
        f"{current.point(1).emergency_runway_months:.1f} months on the current path. "
        f"{profile.name}'s stated runway goal is {profile.emergency_months_goal} months."
    )

    negative = _first_negative(alternative)
    if negative is not None:
        lowest = min(point.savings for point in alternative.points if point.month >= 1)
        statements.append(
            f"Projected savings fall below zero in month {negative.month} "
            f"and the lowest point inside {horizon} months is {euro(lowest)}."
        )

    current_under = _months_under_goal(current, profile.emergency_months_goal)
    future_under = _months_under_goal(alternative, profile.emergency_months_goal)
    statements.append(
        f"Across the next {horizon} months, emergency runway is under "
        f"{profile.emergency_months_goal} months in {future_under} months on this future "
        f"and in {current_under} months on the current path."
    )
    return statements


def peer_statements(
    profile: CustomerProfile,
    alternative: PathProjection,
    cohort: PeerCohort,
    decisions: tuple[DecisionView, ...],
) -> list[str]:
    decision_ids = {item.id for item in decisions}
    runway = alternative.point(1).emergency_runway_months
    lines = [
        (
            f"The synthetic cohort reflects net income of {cohort.income_band}, a fixed-cost "
            f"ratio around {cohort.fixed_cost_ratio:.0%}, and a savings rate around "
            f"{cohort.savings_rate:.0%}. {profile.name}'s fixed costs are {profile.fixed_cost_ratio:.0%} "
            f"of net income, and the current savings rate is {profile.savings_rate:.0%}."
        )
    ]
    if "car" in decision_ids or "apartment" in decision_ids:
        lines.insert(
            0,
            (
                "Comparable financial profiles typically retain around "
                f"{cohort.runway_after_similar_purchase_months:.1f} months of emergency savings "
                f"after a similar purchase. In this simulation {profile.name} would retain "
                f"approximately {runway:.1f} months one month in."
            ),
        )
    else:
        rate = alternative.point(1).savings_rate
        if rate is None:
            lines.append(
                f"In month 1, {profile.name}'s income on this future is {euro(alternative.point(1).monthly_income)}, "
                "so a savings rate is not defined for that month."
            )
        else:
            lines.append(
                f"The synthetic cohort's typical savings rate is {cohort.savings_rate:.0%}. "
                f"On this future, the month-1 savings rate is {rate:.0%}."
            )
    return lines


def assumption_note(*, rate_label: str, decisions: tuple[DecisionView, ...]) -> str:
    included = ", ".join(item.label.lower() for item in decisions) if decisions else "no extra decision"
    return (
        "Both paths start from today's savings and run for 36 months. "
        f"This future applies {included}. "
        f"Car loans use a mock {rate_label}. "
        "Running costs, when set above zero, stand in for insurance, fuel, and maintenance. "
        "Every figure is synthetic."
    )


def _first_negative(path: PathProjection) -> MonthPoint | None:
    for point in path.points:
        if point.month >= 1 and point.savings < 0:
            return point
    return None


def _months_under_goal(path: PathProjection, goal_months: int) -> int:
    return sum(
        1
        for point in path.points
        if point.month >= 1 and point.emergency_runway_months < goal_months
    )
