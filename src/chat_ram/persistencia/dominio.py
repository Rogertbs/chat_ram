"""Persistência da conversa (estado por thread_id), separada dos dados OTRS."""

from dataclasses import dataclass, field


@dataclass
class EstadoConversa:
    """Estado de uma conversa que sobrevive a fechar e reabrir a interface."""

    fila_selecionada: str | None = None
    ticket_em_foco: str | None = None
    esclarecimentos: list[str] = field(default_factory=list)
