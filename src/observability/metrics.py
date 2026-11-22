from dataclasses import dataclass


@dataclass
class ModelMetrics:
    duration_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "local-deterministic"
    # Unknown provider pricing is represented as zero plus the model name; never fabricated.
    estimated_cost_usd: float = 0.0

    @property
    def output_tokens_per_second(self) -> float:
        return self.output_tokens / (self.duration_ms / 1000) if self.duration_ms > 0 else 0.0
