"""Avalia o agente com o DeepEval e imprime uma tabela por versão do modelo e por split.

Uso:
    python eval/run_eval.py                 # versões 1 e 2, dev e teste
    python eval/run_eval.py --versao 2 --falhas dev
    python eval/run_eval.py --versao 2 --falhas teste    # só olhe depois de fechar a versão

Sem chave e sem rede: as métricas são regras, não um LLM juiz.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deepeval import evaluate  # noqa: E402
from deepeval.evaluate.configs import AsyncConfig, CacheConfig, DisplayConfig  # noqa: E402

from agente.tracing import finalizar, registrar_nota  # noqa: E402
from eval.execucao import HANDLERS, montar_casos_de_teste  # noqa: E402
from eval.metricas import TODAS  # noqa: E402


def avaliar(versao: int) -> list[dict]:
    """Devolve, por caso, o nome, o split e a nota/motivo de cada métrica."""
    casos = montar_casos_de_teste(versao)
    saida = evaluate(
        test_cases=casos,
        metrics=[m() for m in TODAS],
        async_config=AsyncConfig(run_async=False),
        display_config=DisplayConfig(show_indicator=False, print_results=False),
        cache_config=CacheConfig(write_cache=False, use_cache=False),  # sem cache em disco: a 2ª execução falhava com ele
    )
    por_nome = {c.name: c for c in casos}
    linhas = []
    for r in saida.test_results:
        for d in r.metrics_data:  # com Langfuse ligado, cada nota vai para o trace do caso
            registrar_nota(HANDLERS.get(r.name), d.name, d.score, d.reason)
        linhas.append({
            "caso": r.name,
            "split": por_nome[r.name].metadata["split"],
            "entrada": por_nome[r.name].input,
            "metricas": {d.name: {"nota": d.score, "motivo": d.reason} for d in r.metrics_data},
        })
    return sorted(linhas, key=lambda x: x["caso"])


def media(linhas: list[dict], metrica: str) -> float:
    notas = [l["metricas"][metrica]["nota"] for l in linhas]
    return sum(notas) / len(notas)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--versao", type=int, choices=[1, 2], help="só uma versão do modelo (padrão: as duas)")
    p.add_argument("--falhas", choices=["dev", "teste"], help="lista os casos com nota abaixo de 1 nesse split")
    p.add_argument("--json", help="grava o resultado completo neste arquivo")
    args = p.parse_args()

    nomes = [m.nome for m in TODAS]
    completo = {}
    for versao in ([args.versao] if args.versao else [1, 2]):
        linhas = avaliar(versao)
        completo[f"versao{versao}"] = linhas
        print(f"\n=== modelo de regras v{versao} ===")
        print(f"{'split':<7}{'casos':>6}  " + "  ".join(f"{n[:22]:>22}" for n in nomes))
        for split in ("dev", "teste"):
            sub = [l for l in linhas if l["split"] == split]
            print(f"{split:<7}{len(sub):>6}  " + "  ".join(f"{media(sub, n):>22.3f}" for n in nomes))
        if args.falhas:
            print(f"\nCasos com alguma nota abaixo de 1 ({args.falhas}):")
            for l in linhas:
                if l["split"] != args.falhas:
                    continue
                for n, d in l["metricas"].items():
                    if d["nota"] < 1:
                        print(f"  {l['caso']}  {n}: {d['nota']:.2f}  {d['motivo']}  | {l['entrada'][:70]}")
    finalizar()
    if args.json:
        Path(args.json).write_text(json.dumps(completo, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
