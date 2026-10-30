"""Rastreamento com Langfuse, ligado só se as chaves estiverem no ambiente.

Sem `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY`, nada aqui faz nada e o agente roda igual. Com elas, o
`CallbackHandler` do Langfuse registra uma observação por nó do grafo (entrada, saída, tempo), e as notas do
DeepEval podem ser penduradas no trace de cada caso.
"""
import os


def ativo() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def novo_handler():
    """Um handler por execução (um trace por mensagem). Devolve None se o rastreamento estiver desligado."""
    if not ativo():
        return None
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


def registrar_nota(handler, nome: str, valor: float, comentario: str | None = None) -> None:
    """Pendura uma nota (0 a 1) no trace da execução que o handler acompanhou."""
    if handler is None or getattr(handler, "last_trace_id", None) is None:
        return
    from langfuse import get_client

    get_client().create_score(trace_id=handler.last_trace_id, name=nome, value=float(valor), comment=comentario)


def finalizar() -> None:
    """Manda para o servidor o que ainda está na fila. Chame antes de o processo terminar."""
    if ativo():
        from langfuse import get_client

        get_client().flush()
