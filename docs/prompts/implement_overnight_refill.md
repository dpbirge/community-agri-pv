# Prompt: Implement Tank TDS Overnight Refill

Read the implementation plan at `docs/plans/tank_tds_overnight_refill.md` and implement all 9 steps. The plan replaces the current look-ahead drain and safety flush logic in `src/water.py` with a mass-balance overnight refill step that remixes tank TDS for the next day without wasting water. Key files: `src/water.py`, `src/water_balance.py`. After implementation, run `python -m src.water_balance` to verify conservation (balance_check max ≈ 0) and check that deficit totals are reasonable. Then run `python -m pytest tests/` to catch any breakage.
