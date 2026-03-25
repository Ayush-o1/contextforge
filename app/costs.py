# Per-token costs in USD (update as providers change pricing)
COST_TABLE = {
    "gpt-4o":            {"prompt": 5.00 / 1e6,  "completion": 15.00 / 1e6},
    "gpt-3.5-turbo":     {"prompt": 0.50 / 1e6,  "completion": 1.50 / 1e6},
    "claude-opus-4-5":   {"prompt": 15.00 / 1e6, "completion": 75.00 / 1e6},
    "claude-haiku-4-5":  {"prompt": 0.80 / 1e6,  "completion": 4.00 / 1e6},
}

def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = COST_TABLE.get(model, {"prompt": 0, "completion": 0})
    return (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])