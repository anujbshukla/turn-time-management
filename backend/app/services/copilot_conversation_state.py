@dataclass
class ConversationState:
    intent: str | None = None
    metric: str | None = None
    group_by: str | None = None
    filters: dict = field(default_factory=dict)
    limit: int = 5