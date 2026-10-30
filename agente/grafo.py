"""O grafo do agente, em LangGraph.

Fluxo: classificar -> (pedido de compra) extrair -> validar -> aprovação humana -> enviar cotação.
Dúvida, cobrança e conversa solta não geram envio. O envio só acontece depois de uma resposta "OK" de
uma pessoa, e o nó que envia confere isso de novo no código (a trava não depende do roteamento do grafo).
"""
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .modelos import Modelo
from .validacao import validar


class Estado(TypedDict, total=False):
    mensagem: str
    categoria: str
    itens: list
    erros: list
    aprovacao: str
    cotacao_enviada: bool
    resposta: str
    trilha: Annotated[list, operator.add]  # cada nó acrescenta o próprio nome; as listas são somadas


def enviar_cotacao(estado: Estado):
    """Único ponto que "envia". Confere a aprovação de novo, mesmo que o grafo já tenha roteado só os "OK"."""
    if estado.get("aprovacao") != "OK":
        raise PermissionError("envio de cotação sem aprovação humana")
    return {
        "cotacao_enviada": True,
        "resposta": f"Cotação enviada ({len(estado['itens'])} item(ns)).",
        "trilha": ["enviar_cotacao"],
    }


def montar(modelo: Modelo, checkpointer=None):
    """Monta e compila o grafo. O checkpointer é obrigatório para o `interrupt` (a pausa) funcionar."""

    def classificar(estado: Estado):
        return {"categoria": modelo.classificar(estado["mensagem"]), "trilha": ["classificar"]}

    def extrair(estado: Estado):
        return {"itens": modelo.extrair_itens(estado["mensagem"]), "trilha": ["extrair"]}

    def validar_itens(estado: Estado):
        return {"erros": validar(estado["itens"]), "trilha": ["validar"]}

    def pedir_correcao(estado: Estado):
        return {
            "cotacao_enviada": False,
            "resposta": "Pedido não enviado. " + " ".join(estado["erros"]),
            "trilha": ["pedir_correcao"],
        }

    def aprovacao_humana(estado: Estado):
        # Pausa o grafo aqui. Quem chamou recebe o que mostrar à pessoa; o valor de retomada vira `decisao`.
        decisao = interrupt({"pergunta": "Aprovar o envio da cotação?", "itens": estado["itens"]})
        return {"aprovacao": str(decisao).strip().upper(), "trilha": ["aprovacao_humana"]}

    def recusar(estado: Estado):
        return {"cotacao_enviada": False, "resposta": "Cotação cancelada: sem aprovação.", "trilha": ["recusar"]}

    def responder_duvida(estado: Estado):
        return {"resposta": modelo.responder_duvida(estado["mensagem"]), "trilha": ["responder_duvida"]}

    def encaminhar(estado: Estado):
        return {"resposta": "Mensagem encaminhada ao responsável.", "trilha": ["encaminhar"]}

    def rota_categoria(estado: Estado):
        return {
            "pedido_compra": "extrair",
            "duvida_tecnica": "responder_duvida",
        }.get(estado["categoria"], "encaminhar")

    def rota_validacao(estado: Estado):
        return "pedir_correcao" if estado["erros"] else "aprovacao_humana"

    def rota_aprovacao(estado: Estado):
        return "enviar_cotacao" if estado["aprovacao"] == "OK" else "recusar"

    g = StateGraph(Estado)
    for nome, funcao in {
        "classificar": classificar, "extrair": extrair, "validar_itens": validar_itens,
        "pedir_correcao": pedir_correcao, "aprovacao_humana": aprovacao_humana,
        "enviar_cotacao": enviar_cotacao, "recusar": recusar,
        "responder_duvida": responder_duvida, "encaminhar": encaminhar,
    }.items():
        g.add_node(nome, funcao)

    g.add_edge(START, "classificar")
    g.add_conditional_edges("classificar", rota_categoria, ["extrair", "responder_duvida", "encaminhar"])
    g.add_edge("extrair", "validar_itens")
    g.add_conditional_edges("validar_itens", rota_validacao, ["pedir_correcao", "aprovacao_humana"])
    g.add_conditional_edges("aprovacao_humana", rota_aprovacao, ["enviar_cotacao", "recusar"])
    for fim in ("pedir_correcao", "enviar_cotacao", "recusar", "responder_duvida", "encaminhar"):
        g.add_edge(fim, END)

    return g.compile(checkpointer=checkpointer or InMemorySaver())


def executar(grafo, mensagem: str, thread_id: str, aprovacao: str | None = None, callbacks=None) -> dict:
    """Roda uma mensagem. Se o grafo parar na aprovação e `aprovacao` vier, retoma com ela.

    Devolve o estado final mais `pausado` (True se parou esperando a pessoa) e `pergunta`.
    """
    config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks or []}
    saida = grafo.invoke({"mensagem": mensagem, "trilha": []}, config)
    pausado = bool(saida.get("__interrupt__"))
    pergunta = saida["__interrupt__"][0].value if pausado else None
    if pausado and aprovacao is not None:
        saida = grafo.invoke(Command(resume=aprovacao), config)
        pausado = bool(saida.get("__interrupt__"))
        pergunta = saida["__interrupt__"][0].value if pausado else None
    resultado = {k: v for k, v in saida.items() if k != "__interrupt__"}
    resultado["pausado"] = pausado
    resultado["pergunta"] = pergunta
    return resultado


def retomar(grafo, thread_id: str, aprovacao: str, callbacks=None) -> dict:
    """Responde a uma pausa que ficou esperando a pessoa, na mesma conversa (mesmo thread_id)."""
    config = {"configurable": {"thread_id": thread_id}, "callbacks": callbacks or []}
    saida = grafo.invoke(Command(resume=aprovacao), config)
    resultado = {k: v for k, v in saida.items() if k != "__interrupt__"}
    resultado["pausado"] = bool(saida.get("__interrupt__"))
    resultado["pergunta"] = saida["__interrupt__"][0].value if resultado["pausado"] else None
    return resultado
