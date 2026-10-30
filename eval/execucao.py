"""Roda o grafo sobre os casos de `casos.json` e monta os casos de teste do DeepEval."""
import json
from pathlib import Path

from deepeval.test_case import LLMTestCase

from agente.grafo import executar, montar
from agente.modelos import ModeloRegras
from agente.tracing import novo_handler

CASOS = Path(__file__).with_name("casos.json")

# Handler do Langfuse de cada caso (vazio se o rastreamento estiver desligado), para pendurar as notas depois.
HANDLERS: dict = {}


def carregar_casos() -> list[dict]:
    return json.loads(CASOS.read_text(encoding="utf-8"))["casos"]


def montar_casos_de_teste(versao: int, casos: list[dict] | None = None) -> list[LLMTestCase]:
    grafo = montar(ModeloRegras(versao))
    resultado = []
    for c in casos if casos is not None else carregar_casos():
        esperado = dict(c["esperado"])
        esperado["pausado"] = esperado["categoria"] == "pedido_compra" and not esperado["tem_erro"]

        # Três execuções do mesmo pedido, cada uma com um desfecho da pessoa: sem resposta, NÃO e OK.
        handler = novo_handler()
        HANDLERS[c["id"]] = handler
        sem_resposta = executar(grafo, c["mensagem"], f"{c['id']}-semresposta", callbacks=[handler] if handler else None)
        com_nao = executar(grafo, c["mensagem"], f"{c['id']}-nao", aprovacao="NAO")
        com_ok = executar(grafo, c["mensagem"], f"{c['id']}-ok", aprovacao="OK")

        real = {
            "categoria": sem_resposta["categoria"],
            "itens": sem_resposta.get("itens", []),
            "tem_erro": bool(sem_resposta.get("erros")),
            "pausado": sem_resposta["pausado"],
        }
        resultado.append(LLMTestCase(
            name=c["id"],
            input=c["mensagem"],
            actual_output=json.dumps(real, ensure_ascii=False),
            expected_output=json.dumps(esperado, ensure_ascii=False),
            metadata={
                "split": c["split"],
                "enviada_antes_da_aprovacao": sem_resposta.get("cotacao_enviada") is True,
                "enviada_apos_nao": com_nao.get("cotacao_enviada") is True,
                "enviada_com_ok": com_ok.get("cotacao_enviada") is True,
            },
            tags=[c["split"]],
        ))
    return resultado
