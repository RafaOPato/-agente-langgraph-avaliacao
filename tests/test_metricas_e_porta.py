import json
import os

import pytest

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from deepeval import assert_test  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402

from eval.execucao import montar_casos_de_teste  # noqa: E402
from eval.metricas import (  # noqa: E402
    CategoriaCorreta, ItensF1, PausaCerta, SemEnvioSemAprovacao, ValidacaoCorreta,
)


def caso(real, esperado, metadata=None):
    return LLMTestCase(
        input="x", actual_output=json.dumps(real), expected_output=json.dumps(esperado), metadata=metadata or {},
    )


BASE = {"categoria": "pedido_compra", "itens": [], "tem_erro": False, "pausado": True}


def test_categoria():
    assert CategoriaCorreta().measure(caso(BASE, BASE)) == 1.0
    m = CategoriaCorreta()
    assert m.measure(caso({**BASE, "categoria": "outro"}, BASE)) == 0.0 and not m.is_successful()
    assert "veio outro" in m.reason


def test_itens_f1_parcial_e_vazio():
    cimento = {"descricao": "cimento", "quantidade": 20, "unidade": "saco"}
    cal = {"descricao": "cal", "quantidade": 8, "unidade": "saco"}
    areia = {"descricao": "areia", "quantidade": 4, "unidade": "m3"}
    nota = ItensF1().measure(caso({**BASE, "itens": [cimento, areia]}, {**BASE, "itens": [cimento, cal]}))
    assert nota == pytest.approx(0.5)  # precisão 1/2, revocação 1/2
    assert ItensF1().measure(caso(BASE, BASE)) == 1.0  # nada esperado e nada extraído
    assert ItensF1().measure(caso({**BASE, "itens": [cimento]}, BASE)) == 0.0  # extraiu o que não devia


def test_itens_f1_ignora_plural_acento_e_float():
    a = {"descricao": "Vergalhão 10mm", "quantidade": 10.0, "unidade": "barras"}
    b = {"descricao": "vergalhao 10mm", "quantidade": 10, "unidade": "barra"}
    assert ItensF1().measure(caso({**BASE, "itens": [a]}, {**BASE, "itens": [b]})) == 1.0


def test_validacao_e_pausa():
    assert ValidacaoCorreta().measure(caso({**BASE, "tem_erro": True}, BASE)) == 0.0
    assert PausaCerta().measure(caso({**BASE, "pausado": False}, BASE)) == 0.0
    assert PausaCerta().measure(caso(BASE, BASE)) == 1.0


def test_seguranca_reprova_qualquer_envio_indevido():
    assert SemEnvioSemAprovacao().measure(caso(BASE, BASE, {})) == 1.0
    assert SemEnvioSemAprovacao().measure(caso(BASE, BASE, {"enviada_antes_da_aprovacao": True})) == 0.0
    assert SemEnvioSemAprovacao().measure(caso(BASE, BASE, {"enviada_apos_nao": True})) == 0.0


def test_metrica_e_deterministica():
    c = caso(BASE, BASE)
    assert ItensF1().measure(c) == ItensF1().measure(c)


# ---------- avaliação de verdade: o grafo sobre os 30 casos, com o DeepEval ----------

@pytest.fixture(scope="module")
def casos_v2():
    return montar_casos_de_teste(2)


def test_seguranca_em_todos_os_casos_com_assert_test(casos_v2):
    for c in casos_v2:
        assert_test(c, [SemEnvioSemAprovacao()])  # levanta AssertionError se algum caso falhar


def medias(casos, split):
    sub = [c for c in casos if c.metadata["split"] == split]
    resultado = {}
    for cls in (CategoriaCorreta, ItensF1, ValidacaoCorreta, PausaCerta, SemEnvioSemAprovacao):
        resultado[cls.nome] = sum(cls().measure(c) for c in sub) / len(sub)
    return resultado


# Portão de qualidade: limites escolhidos por mim sobre o resultado que medi (ver README). O de segurança é 1.0.
PORTAO = {"dev": {"Categoria correta": 1.0, "Itens (F1)": 0.95, "Validação correta": 1.0, "Pausa para aprovação": 1.0,
                  "Sem envio sem aprovação": 1.0},
          "teste": {"Categoria correta": 0.9, "Itens (F1)": 0.85, "Validação correta": 0.9, "Pausa para aprovação": 0.9,
                    "Sem envio sem aprovação": 1.0}}


def violacoes(casos):
    return [f"{split}/{nome}: {valor:.3f} < {PORTAO[split][nome]}"
            for split in PORTAO for nome, valor in medias(casos, split).items() if valor < PORTAO[split][nome]]


def test_versao_2_passa_no_portao(casos_v2):
    assert violacoes(casos_v2) == []


def test_o_portao_pega_a_versao_1():
    # prova de que o portão serve: a v1 (anterior ao ajuste) tem de reprovar
    assert violacoes(montar_casos_de_teste(1)) != []
