"""Drive the dark factory programmatically.

Runs entirely in MOCK mode if no OLLAMA_API_KEY is set, so it works offline.

    python examples/build_a_feature.py
"""
from __future__ import annotations

from nyx import Factory, load_config


def main() -> None:
    cfg = load_config()
    # Keep the example fully autonomous + small so it runs end to end offline.
    cfg.autonomy = "autonomous"
    cfg.fanout = 3

    factory = Factory(config=cfg)
    result = factory.build(
        "Add a usage-based billing dashboard with Stripe metering"
    )

    print(result.summary())
    print("\nMetrics:", result.metrics)
    print("Audit ledger intact:", result.ledger_ok)

    spec = result.artifact("design")
    if spec:
        print("\n----- DESIGN ARTIFACT (excerpt) -----")
        print(spec[:400])


if __name__ == "__main__":
    main()
