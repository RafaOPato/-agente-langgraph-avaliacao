"""Roda o agente numa mensagem, no terminal.

    python run.py "manda 3 rolos de manta asfaltica"
    python run.py "manda 3 rolos de manta asfaltica" --aprovacao OK      # responde a pausa sem perguntar
    python run.py "preciso de 10 cimento" --versao 1

Sem --aprovacao, se o grafo parar na aprovação o script pergunta no terminal.
"""
import argparse
import sys
import uuid

from agente.grafo import executar, montar, retomar
from agente.modelos import ModeloRegras
from agente.tracing import finalizar, novo_handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mensagem")
    p.add_argument("--versao", type=int, choices=[1, 2], default=2)
    p.add_argument("--aprovacao", help="resposta da pessoa à pausa (OK para aprovar)")
    args = p.parse_args()

    grafo = montar(ModeloRegras(args.versao))
    handler = novo_handler()
    callbacks = [handler] if handler else None
    thread = uuid.uuid4().hex

    r = executar(grafo, args.mensagem, thread, callbacks=callbacks)
    if r["pausado"]:
        print("Parou para aprovação humana. Itens:")
        for item in r["pergunta"]["itens"]:
            print(f"  - {item['quantidade']} {item['unidade']} de {item['descricao']}")
        resposta = args.aprovacao if args.aprovacao is not None else input("Aprovar o envio? (OK/NAO) ").strip()
        r = retomar(grafo, thread, resposta, callbacks=callbacks)
    print("categoria:", r["categoria"])
    print("trilha:   ", " > ".join(r["trilha"]))
    print("resposta: ", r["resposta"])
    finalizar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
