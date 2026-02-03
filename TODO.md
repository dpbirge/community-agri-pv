By David - Tue Feb 3, 2026

General todo list:
- Move water data and metadata notes from water_policy_only.yaml to data folder
- Figure out a way to test policies and outputs without creating unit tests that are always passed... we need some kind of detailed tracking/plotting that will visually show policies being implemented and triggered in real time (maybe a box plot or something) or a logging output per farm that tracks all policies visually

Water policy todo list:
- Add physical and legal constraints such as max water per day draw, treatment plant throughput limits, qoutas
- Add seasonal water and power prices changes (if research in Egypt suggests this is typical)
- Water and energy demand tier pricing (based on research)
- Look into water policies and create more real hybrid policies with multiple triggers/decision points
- Risk-aware and price-aware water use policies (if water price drops, change mix)
- Sensitivity analysis