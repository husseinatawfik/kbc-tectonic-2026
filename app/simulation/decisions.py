"""Turn form inputs into adjustments on the shared projection."""

from app.simulation.engine import SimulationInputError, money, monthly_payment
from app.simulation.explain import euro
from app.simulation.models import CustomerProfile, DecisionView, MonthlyAdjustment


class BuiltDecision:
    def __init__(self, view: DecisionView, adjustments: tuple[MonthlyAdjustment, ...]):
        self.view = view
        self.adjustments = adjustments


def decisions_from_payload(
    profile: CustomerProfile,
    payload: dict,
    *,
    annual_interest_rate: float,
) -> list[BuiltDecision]:
    if not isinstance(payload, dict):
        raise SimulationInputError("Request body must be a JSON object.")

    built: list[BuiltDecision] = []
    car = _section(payload, "car")
    if _enabled(car):
        built.append(_car(car, annual_interest_rate))
    apartment = _section(payload, "apartment")
    if _enabled(apartment):
        built.append(_apartment(apartment))
    leave = _section(payload, "leave")
    if _enabled(leave):
        built.append(_leave(profile, leave))
    spending = _section(payload, "spending")
    if _enabled(spending):
        built.append(_spending(profile, spending))
    return built


def future_label(decisions: list[BuiltDecision]) -> str:
    if not decisions:
        return "Same path"
    if len(decisions) == 1:
        return decisions[0].view.label
    return "Combined future"


def _section(payload: dict, key: str) -> dict:
    raw = payload.get(key, {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SimulationInputError(f"The {key} decision must be an object.")
    return raw


def _enabled(section: dict) -> bool:
    return bool(section.get("enabled"))


def _number(section: dict, key: str, label: str) -> float:
    try:
        value = section[key]
        if isinstance(value, bool):
            raise TypeError
        return float(value)
    except (KeyError, TypeError, ValueError) as error:
        raise SimulationInputError(f"Enter a valid {label}.") from error


def _whole(section: dict, key: str, label: str) -> int:
    try:
        value = section[key]
        if isinstance(value, bool):
            raise TypeError
        number = float(value)
        if not number.is_integer():
            raise TypeError
        return int(number)
    except (KeyError, TypeError, ValueError) as error:
        raise SimulationInputError(f"Enter a valid {label}.") from error


def _car(section: dict, annual_interest_rate: float) -> BuiltDecision:
    price = _number(section, "price", "car price")
    down_payment = _number(section, "down_payment", "down payment")
    loan_years = _whole(section, "loan_years", "loan duration")
    running = _number(section, "running_cost", "monthly running cost")

    if price <= 0 or price > 80000:
        raise SimulationInputError("Car price must be between €1 and €80,000.")
    if down_payment < 0:
        raise SimulationInputError("Down payment cannot be negative.")
    if loan_years < 1 or loan_years > 10:
        raise SimulationInputError("Loan duration must be between 1 and 10 years.")
    if running < 0 or running > 800:
        raise SimulationInputError("Monthly running costs must be between €0 and €800.")
    if annual_interest_rate < 0 or annual_interest_rate > 0.25:
        raise SimulationInputError("Interest rate is outside the demo range.")

    down = money(min(down_payment, price))
    principal = money(price - down)
    term_months = loan_years * 12
    payment = monthly_payment(principal, annual_interest_rate, term_months)
    rate_label = f"{annual_interest_rate:.1%} APR"
    total_paid = money(payment * term_months)
    interest = money(total_paid - principal)

    sentences = [
        f"The price is {euro(price)}. Month 1 withdraws a down payment of {euro(down)} and finances {euro(principal)}."
    ]
    if payment > 0:
        sentences.append(
            f"The mock {rate_label} loan payment is {euro(payment)} for {term_months} months. "
            f"Payments over the full term add up to {euro(total_paid)}, including {euro(interest)} of interest."
        )
    else:
        sentences.append("Nothing is financed, so there is no loan payment.")
    if running > 0:
        sentences.append(
            f"Running costs of {euro(running)} each month stand in for insurance, fuel, and maintenance. "
            "They continue after the loan ends."
        )
    else:
        sentences.append("Running costs are €0, so insurance, fuel, and maintenance are not included.")

    adjustments = [
        MonthlyAdjustment(
            opening_savings_delta=-down,
            extra_monthly_expense=payment,
            loan_payment=payment,
            start_month=1,
            end_month=term_months,
        )
    ]
    if running > 0:
        adjustments.append(
            MonthlyAdjustment(
                extra_monthly_expense=running,
                start_month=1,
                end_month=None,
            )
        )
    return BuiltDecision(DecisionView("car", "Buy a car", " ".join(sentences)), tuple(adjustments))


def _apartment(section: dict) -> BuiltDecision:
    extra_rent = _number(section, "extra_rent", "extra rent")
    deposit = _number(section, "deposit", "rental deposit")
    if extra_rent < 0 or extra_rent > 2000:
        raise SimulationInputError("Extra rent must be between €0 and €2,000 a month.")
    if deposit < 0 or deposit > 20000:
        raise SimulationInputError("The rental deposit must be between €0 and €20,000.")
    if extra_rent == 0 and deposit == 0:
        raise SimulationInputError("Set extra rent or a deposit for the apartment, or turn it off.")

    deposit_sentence = (
        f"A deposit of {euro(deposit)} is withdrawn from savings in month 1."
        if deposit
        else "No extra deposit is withdrawn."
    )
    detail = (
        f"Housing costs {euro(extra_rent)} more each month than on the current path. {deposit_sentence}"
    )
    return BuiltDecision(
        DecisionView("apartment", "More expensive apartment", detail),
        (
            MonthlyAdjustment(
                opening_savings_delta=-deposit,
                extra_monthly_expense=extra_rent,
                start_month=1,
                end_month=None,
            ),
        ),
    )


def _leave(profile: CustomerProfile, section: dict) -> BuiltDecision:
    months = _whole(section, "months", "time away")
    kept_percent = _number(section, "income_kept_percent", "income kept")
    if months < 1 or months > 24:
        raise SimulationInputError("Time away must be between 1 and 24 months.")
    if kept_percent < 0 or kept_percent > 100:
        raise SimulationInputError("Income kept must be between 0% and 100%.")

    kept_income = money(profile.monthly_net_income * kept_percent / 100)
    income_delta = money(kept_income - profile.monthly_net_income)
    detail = (
        f"For {months} months, net income is {euro(kept_income)} instead of {euro(profile.monthly_net_income)}. "
        "Income then returns to the current amount."
    )
    return BuiltDecision(
        DecisionView("leave", "Time away from work", detail),
        (
            MonthlyAdjustment(
                income_delta=income_delta,
                start_month=1,
                end_month=months,
            ),
        ),
    )


def _spending(profile: CustomerProfile, section: dict) -> BuiltDecision:
    variable = _number(section, "variable", "monthly spending")
    if variable < 0 or variable > 5000:
        raise SimulationInputError("Monthly variable spending must be between €0 and €5,000.")

    delta = money(variable - profile.monthly_variable)
    if delta == 0:
        change = f"Variable spending stays at {euro(profile.monthly_variable)}."
    elif delta < 0:
        change = (
            f"Variable spending is {euro(variable)} instead of {euro(profile.monthly_variable)}, "
            f"which leaves {euro(-delta)} more after expenses each month."
        )
    else:
        change = (
            f"Variable spending is {euro(variable)} instead of {euro(profile.monthly_variable)}, "
            f"which uses {euro(delta)} more each month."
        )
    return BuiltDecision(
        DecisionView("spending", "Different spending", change),
        (
            MonthlyAdjustment(
                extra_monthly_expense=delta,
                start_month=1,
                end_month=None,
            ),
        ),
    )
