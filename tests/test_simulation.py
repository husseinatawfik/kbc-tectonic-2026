"""Deterministic checks for the projection engine and the demo API."""

import json
import threading
import unittest
from urllib.request import Request, urlopen

from app.data.synthetic import ALEX, AS_OF, MOCK_CAR_APR
from app.server import make_server, simulate_request
from app.simulation.engine import SimulationInputError, monthly_payment, project_path
from app.simulation.models import MonthlyAdjustment

FORBIDDEN = (
    "bad decision",
    "you should",
    "you shouldn't",
    "don't buy",
    "do not buy",
    "poor choice",
    "mistake",
    "irresponsible",
    "unwise",
    "we recommend",
)


def simulate(**overrides):
    payload = {
        "profile": "alex",
        "car": {
            "enabled": True,
            "price": 30000,
            "down_payment": 5000,
            "loan_years": 5,
            "running_cost": 0,
        },
    }
    payload.update(overrides)
    return simulate_request(payload)


class PaymentTests(unittest.TestCase):
    def test_known_amortization(self):
        principal = 10000
        annual = 0.06
        months = 36
        monthly_rate = annual / 12
        growth = (1 + monthly_rate) ** months
        expected = round(principal * monthly_rate * growth / (growth - 1), 2)
        self.assertEqual(monthly_payment(principal, annual, months), expected)
        self.assertEqual(expected, 304.22)

    def test_zero_interest_splits_evenly(self):
        self.assertEqual(monthly_payment(10000, 0, 2), 5000)


class ProjectionTests(unittest.TestCase):
    def test_current_path_saves_the_full_surplus(self):
        result = simulate(car={"enabled": False})
        current = result["scenarios"][0]
        future = result["scenarios"][1]
        self.assertEqual(current["savings_after_1_year"], 18500 + 900 * 12)
        self.assertEqual(current["savings_after_3_years"], 18500 + 900 * 36)
        self.assertEqual(current["months_to_apartment_goal"], 24)
        self.assertEqual(current["apartment_goal_date"], "2028-09-30")
        self.assertEqual(current["monthly_disposable_income"], 900)
        self.assertEqual(future["label"], "Same path")
        self.assertEqual(future["series"], current["series"])
        self.assertEqual(result["customer"]["emergency_runway_months"], round(18500 / 2300, 2))

    def test_car_withdraws_the_down_payment_and_charges_the_loan(self):
        result = simulate()
        car = result["scenarios"][1]
        payment = monthly_payment(25000, MOCK_CAR_APR, 60)
        self.assertEqual(car["label"], "Buy a car")
        self.assertEqual(car["series"][0]["savings"], 18500)
        self.assertEqual(car["series"][1]["savings"], round(18500 - 5000 + (900 - payment), 2))
        self.assertEqual(car["series"][1]["loan_payment"], payment)
        self.assertLess(car["savings_after_3_years"], result["scenarios"][0]["savings_after_3_years"])
        self.assertGreater(car["months_to_apartment_goal"], 24)
        self.assertIn("including", car["decisions"][0]["detail"])

    def test_running_costs_continue_after_the_loan(self):
        result = simulate(
            car={
                "enabled": True,
                "price": 12000,
                "down_payment": 2000,
                "loan_years": 1,
                "running_cost": 100,
            }
        )
        future = result["scenarios"][1]
        payment = monthly_payment(10000, MOCK_CAR_APR, 12)
        self.assertEqual(future["series"][12]["loan_payment"], payment)
        self.assertEqual(future["series"][12]["monthly_disposable_income"], round(900 - payment - 100, 2))
        self.assertEqual(future["series"][13]["loan_payment"], 0)
        self.assertEqual(future["series"][13]["monthly_disposable_income"], 800)
        self.assertIn("continue after the loan", future["decisions"][0]["detail"])

    def test_apartment_rent_and_deposit(self):
        result = simulate(
            car={"enabled": False},
            apartment={"enabled": True, "extra_rent": 400, "deposit": 2000},
        )
        future = result["scenarios"][1]
        self.assertEqual(future["label"], "More expensive apartment")
        self.assertEqual(future["series"][1]["savings"], 18500 - 2000 + (900 - 400))
        self.assertEqual(future["monthly_disposable_income"], 500)
        self.assertGreater(future["months_to_apartment_goal"], 24)

    def test_leave_restores_income(self):
        result = simulate(
            car={"enabled": False},
            leave={"enabled": True, "months": 6, "income_kept_percent": 0},
        )
        future = result["scenarios"][1]
        self.assertEqual(future["series"][6]["monthly_income"], 0)
        self.assertEqual(future["series"][6]["monthly_disposable_income"], -2300)
        self.assertEqual(future["series"][6]["savings_rate"], None)
        self.assertEqual(future["savings_rate_month_one_label"], "not defined")
        self.assertEqual(future["series"][7]["monthly_disposable_income"], 900)
        self.assertLess(future["series"][6]["savings"], future["series"][0]["savings"])

    def test_lower_spending_raises_the_savings_rate(self):
        result = simulate(
            car={"enabled": False},
            spending={"enabled": True, "variable": 650},
        )
        future = result["scenarios"][1]
        self.assertEqual(future["series"][1]["monthly_disposable_income"], 1100)
        self.assertEqual(future["series"][1]["savings"], 18500 + 1100)
        self.assertAlmostEqual(future["savings_rate_month_one"], 1100 / 3200, places=4)
        self.assertLess(future["months_to_apartment_goal"], 24)

    def test_decisions_stack(self):
        payment = monthly_payment(20000, MOCK_CAR_APR, 60)
        result = simulate(
            car={
                "enabled": True,
                "price": 25000,
                "down_payment": 5000,
                "loan_years": 5,
                "running_cost": 200,
            },
            leave={"enabled": True, "months": 6, "income_kept_percent": 0},
        )
        future = result["scenarios"][1]
        self.assertEqual(future["label"], "Combined future")
        self.assertEqual(
            future["series"][1]["savings"],
            round(18500 - 5000 + (0 - 2300 - payment - 200), 2),
        )
        self.assertEqual(future["series"][7]["monthly_disposable_income"], round(900 - payment - 200, 2))
        self.assertEqual(len(future["decisions"]), 2)

    def test_down_payment_cannot_exceed_the_price(self):
        result = simulate(
            car={
                "enabled": True,
                "price": 20000,
                "down_payment": 50000,
                "loan_years": 4,
                "running_cost": 0,
            }
        )
        detail = result["scenarios"][1]["decisions"][0]["detail"]
        self.assertIn("finances €0", detail)
        self.assertIn("no loan payment", detail)

    def test_sam_reaches_a_smaller_deposit_on_a_thinner_buffer(self):
        result = simulate(profile="sam", car={"enabled": False})
        current = result["scenarios"][0]
        self.assertEqual(result["customer"]["name"], "Sam")
        self.assertEqual(result["customer"]["emergency_runway_months"], round(6200 / 3200, 2))
        self.assertEqual(current["months_to_apartment_goal"], 21)
        self.assertEqual(current["apartment_goal_date"], "2028-06-30")
        self.assertIn("€3,800–€4,400", result["peers"]["statements"][0])
        self.assertIn("20%", result["peers"]["statements"][1])

    def test_negative_savings_are_named(self):
        result = simulate(
            profile="sam",
            car={
                "enabled": True,
                "price": 50000,
                "down_payment": 1000,
                "loan_years": 7,
                "running_cost": 400,
            },
            leave={"enabled": True, "months": 8, "income_kept_percent": 0},
        )
        future = result["scenarios"][1]
        negative = next(point for point in future["series"] if point["month"] and point["savings"] < 0)
        text = " ".join(result["comparison"]["statements"])
        self.assertIn(f"fall below zero in month {negative['month']}", text)

    def test_same_inputs_always_match(self):
        self.assertEqual(simulate(), simulate())

    def test_income_gap_uses_the_same_adjustment_model(self):
        gap = MonthlyAdjustment(income_delta=-ALEX.monthly_net_income, start_month=1, end_month=6)
        path = project_path(
            ALEX,
            "leave",
            "Six months away",
            [gap],
            as_of=AS_OF,
            horizon_months=12,
            search_months=36,
        )
        self.assertEqual(path.point(6).monthly_disposable_income, -2300)
        self.assertEqual(path.point(7).monthly_disposable_income, 900)


class LanguageTests(unittest.TestCase):
    def test_copy_describes_tradeoffs_without_advice(self):
        result = simulate(
            apartment={"enabled": True, "extra_rent": 300, "deposit": 1000},
            spending={"enabled": True, "variable": 700},
        )
        chunks = result["comparison"]["statements"] + result["peers"]["statements"]
        chunks += [item["detail"] for item in result["scenarios"][1]["decisions"]]
        text = " ".join(chunks).lower()
        self.assertIn("delays the €40,000 apartment deposit", text)
        self.assertIn("synthetic", result["peers"]["disclaimer"].lower())
        self.assertIn("4.8 months", result["peers"]["statements"][0])
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, text)

    def test_invalid_inputs_are_rejected(self):
        with self.assertRaises(SimulationInputError):
            simulate(car={"enabled": True, "price": 30000, "down_payment": 0, "loan_years": 0, "running_cost": 0})
        with self.assertRaises(SimulationInputError):
            simulate(profile="sam", car={"enabled": False}, leave={"enabled": True, "months": 3, "income_kept_percent": 140})
        with self.assertRaises(SimulationInputError):
            simulate_request({"profile": "jordan"})


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_page_and_simulation_endpoint(self):
        with urlopen(f"http://127.0.0.1:{self.port}/") as response:
            page = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn("KBC Parallel", page)
            self.assertIn("Time away from work", page)
            self.assertIn("/static/app.js", page)

        body = json.dumps(
            {
                "profile": "alex",
                "car": {
                    "enabled": True,
                    "price": 30000,
                    "down_payment": 5000,
                    "loan_years": 5,
                    "running_cost": 220,
                },
                "apartment": {"enabled": True, "extra_rent": 250, "deposit": 1500},
            }
        ).encode()
        request = Request(
            f"http://127.0.0.1:{self.port}/api/simulate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.load(response)
        self.assertEqual(payload["customer"]["name"], "Alex")
        self.assertEqual(payload["scenarios"][1]["label"], "Combined future")
        self.assertEqual(len(payload["scenarios"][1]["decisions"]), 2)
        self.assertNotEqual(
            payload["scenarios"][0]["savings_after_3_years"],
            payload["scenarios"][1]["savings_after_3_years"],
        )

        bad = Request(
            f"http://127.0.0.1:{self.port}/api/simulate",
            data=b"[]",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(Exception) as caught:
            urlopen(bad)
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
