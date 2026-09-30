# KBC Parallel

Hackathon prototype for the KBC Tectonic Hackathon. A fictional customer can compare the path they are already on with a future they assemble: buying a car, moving into a more expensive apartment, taking time away from work, spending a different amount, or any combination of those.

The page shows consequences and trade-offs. It does not recommend a decision.

All banking figures are synthetic. The projection is deterministic Python; the page only displays the API result.

## Run

```bash
python3 -m app.server
```

Open http://127.0.0.1:8080

Alex is the default customer. Sam is a second fictional profile with a thinner cash buffer and a smaller apartment goal. The loan rate is a mock 5.9% APR, not a KBC quote. Car running costs, when set above zero, stand in for insurance, fuel, and maintenance and continue after the loan ends.

## Test

```bash
python3 -m unittest tests.test_simulation
```
