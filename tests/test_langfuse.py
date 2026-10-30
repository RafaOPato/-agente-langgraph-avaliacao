"""Langfuse: desligado sem chaves; ligado, exporta traces e notas. O "servidor" aqui é um HTTP falso local,
então o teste prova que o SDK emite o que deveria, e NÃO que um Langfuse de verdade aceita (ver README)."""
import gzip
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from agente import tracing

RAIZ = Path(__file__).resolve().parent.parent


def test_sem_chaves_o_rastreamento_fica_desligado(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert tracing.ativo() is False
    assert tracing.novo_handler() is None
    tracing.registrar_nota(None, "qualquer", 1.0)  # não faz nada, não levanta
    tracing.finalizar()


def test_so_uma_das_chaves_nao_liga(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-teste")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert tracing.ativo() is False


@pytest.fixture()
def servidor_falso():
    recebidos = []

    class Falso(BaseHTTPRequestHandler):
        def do_POST(self):
            corpo = self.rfile.read(int(self.headers.get("content-length", 0)))
            if self.headers.get("content-encoding") == "gzip":
                corpo = gzip.decompress(corpo)
            recebidos.append((self.path, corpo))
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"successes":[],"errors":[]}')

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Falso)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield servidor.server_address[1], recebidos
    servidor.shutdown()


SCRIPT = """
import sys
sys.path.insert(0, ".")
from eval import run_eval
from agente.tracing import finalizar
run_eval.avaliar(2)
finalizar()
"""


def test_com_chaves_exporta_traces_dos_nos_e_notas_do_deepeval(servidor_falso):
    porta, recebidos = servidor_falso
    ambiente = {**os.environ, "LANGFUSE_PUBLIC_KEY": "pk-lf-teste", "LANGFUSE_SECRET_KEY": "sk-lf-teste",
                "LANGFUSE_HOST": f"http://127.0.0.1:{porta}", "DEEPEVAL_TELEMETRY_OPT_OUT": "YES",
                "PYTHONIOENCODING": "utf-8"}
    # processo separado: o cliente do Langfuse é um singleton e o resto da suíte roda com ele desligado
    saida = subprocess.run([sys.executable, "-c", SCRIPT], cwd=RAIZ, env=ambiente, capture_output=True, timeout=240)
    assert saida.returncode == 0, saida.stderr.decode("utf-8", "replace")[-800:]

    caminhos = {p for p, _ in recebidos}
    assert "/api/public/otel/v1/traces" in caminhos
    assert "/api/public/scores" in caminhos
    traces = b"".join(b for p, b in recebidos if p.endswith("/traces"))
    # só a execução "sem resposta" de cada caso é rastreada: ela para na aprovação, então "enviar_cotacao" não aparece
    for no in (b"classificar", b"extrair", b"validar_itens", b"aprovacao_humana", b"pedir_correcao",
               b"responder_duvida", b"encaminhar"):
        assert no in traces, no
    notas = b"".join(b for p, b in recebidos if p.endswith("/scores"))
    for metrica in ("Categoria correta", "Itens (F1)", "Sem envio sem aprova"):
        assert metrica.encode() in notas, metrica
