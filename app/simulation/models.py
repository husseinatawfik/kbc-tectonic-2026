"""Inputs shared by the simulation engine.

Every life decision is a MonthlyAdjustment on top of the same month-by-month
projection. The page does not invent a second formula per scenario.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerProfile:
    id: str
    name: str
    monthly_net_income: float
    savings: float
    monthly_housing: float
    monthly_fixed_other: float
    monthly_variable: float
    emergency_months_goal: int
    apartment_goal: float

    @property
    def monthly_fixed_costs(self) -> float:
        return self.monthly_housing + self.monthly_fixed_other

    @property
    def monthly_expenses(self) -> float:
        return self.monthly_fixed_costs + self.monthly_variable

    @property
    def monthly_disposable_income(self) -> float:
        return self.monthly_net_income - self.monthly_expenses

    @property
    def fixed_cost_ratio(self) -> float:
        return self.monthly_fixed_costs / self.monthly_net_income

    @property
    def savings_rate(self) -> float:
        return self.monthly_disposable_income / self.monthly_net_income


@dataclass(frozen=True)
class MonthlyAdjustment:
    """A cash-flow change applied on top of the baseline budget.

    opening_savings_delta is applied once, at the start of start_month.
    extra_monthly_expense, income_delta, and loan_payment apply from
    start_month through end_month inclusive. end_month=None means the change
    continues. loan_payment is the portion of extra_monthly_expense that is an
    amortizing loan, so the chart can separate it from other costs.
    """

    opening_savings_delta: float = 0.0
    extra_monthly_expense: float = 0.0
    income_delta: float = 0.0
    loan_payment: float = 0.0
    start_month: int = 1
    end_month: int | None = None

    def recurring_on(self, month: int) -> bool:
        if month < self.start_month:
            return False
        if self.end_month is not None and month > self.end_month:
            return False
        return True


@dataclass(frozen=True)
class DecisionView:
    id: str
    label: str
    detail: str


@dataclass(frozen=True)
class MonthPoint:
    month: int
    savings: float
    monthly_expenses: float
    monthly_disposable_income: float
    emergency_runway_months: float
    loan_payment: float

    @property
    def monthly_income(self) -> float:
        return round(self.monthly_disposable_income + self.monthly_expenses, 2)

    @property
    def savings_rate(self) -> float | None:
        income = self.monthly_income
        if income == 0:
            return None
        return self.monthly_disposable_income / income


@dataclass(frozen=True)
class PathProjection:
    scenario_id: str
    label: str
    points: tuple[MonthPoint, ...]
    decisions: tuple[DecisionView, ...]
    monthly_disposable_income: float
    months_to_apartment_goal: int | None
    apartment_goal_date: object | None

    def point(self, month: int) -> MonthPoint:
        return self.points[month]


@dataclass(frozen=True)
class PeerCohort:
    label: str
    income_band: str
    fixed_cost_ratio: float
    savings_rate: float
    runway_after_similar_purchase_months: float
    traits: tuple[str, ...]
