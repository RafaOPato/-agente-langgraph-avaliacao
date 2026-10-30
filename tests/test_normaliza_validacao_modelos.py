import pytest

from agente.modelos import ModeloRegras
from agente.normaliza import chave_item, normalizar_descricao, normalizar_unidade
from agente.validacao import LIMITE_QUANTIDADE, validar


def test_descricao_ignora_acento_plural_e_artigo():
    assert normalizar_descricao("Vergalhão 10mm") == "vergalhao 10mm"
    assert normalizar_descricao("tijolos 6 furos") == normalizar_descricao("tijolo 6 furo")
    assert normalizar_descricao("pincéis") == "pincel"
    assert normalizar_descricao("argamassa de cimento") == "argamassa cimento"


def test_unidade_normalizada():
    assert normalizar_unidade("Sacos") == "saco"
    assert normalizar_unidade("m³") == "m3"
    assert normalizar_unidade(None) is None


def test_chave_item_trata_quantidade_float_inteira():
    a = {"descricao": "Cimento", "quantidade": 20.0, "unidade": "sacos"}
    b = {"descricao": "cimento", "quantidade": 20, "unidade": "saco"}
    assert chave_item(a) == chave_item(b)


@pytest.mark.parametrize("itens,trecho", [
    ([], "nenhum item"),
    ([{"descricao": "cimento", "quantidade": 10, "unidade": None}], "informe a unidade"),
    ([{"descricao": "cimento", "quantidade": 0, "unidade": "saco"}], "quantidade inválida"),
    ([{"descricao": "cimento", "quantidade": LIMITE_QUANTIDADE + 1, "unidade": "saco"}], "acima do limite"),
    ([{"descricao": "cimento", "quantidade": 5, "unidade": "bandeja"}], "não reconhecida"),
])
def test_validacao_barra(itens, trecho):
    erros = validar(itens)
    assert erros and trecho in " ".join(erros)


def test_validacao_aceita_item_correto_e_o_limite_exato():
    assert validar([{"descricao": "cimento", "quantidade": LIMITE_QUANTIDADE, "unidade": "sacos"}]) == []


def test_versao_invalida():
    with pytest.raises(ValueError):
        ModeloRegras(3)


@pytest.mark.parametrize("mensagem,esperado", [
    ("manda 3 rolos de manta asfaltica", "pedido_compra"),
    ("Qual o traço do concreto pra laje?", "duvida_tecnica"),
    ("o fornecedor do aço ainda não entregou, cobra ele", "cobranca"),
    ("bom dia pessoal", "outro"),
    ("👍", "outro"),
])
def test_classificacao_v2(mensagem, esperado):
    assert ModeloRegras(2).classificar(mensagem) == esperado


def test_extracao_v2_corta_o_prazo_e_reconhece_m3_e_contavel():
    m = ModeloRegras(2)
    itens = m.extrair_itens("Preciso de 20 sacos de cimento CP-II e 5 latas de tinta branca 18L pra sexta")
    assert [chave_item(i) for i in itens] == [("cimento cp-ii", 20, "saco"), ("tinta branca 18l", 5, "lata")]
    assert chave_item(m.extrair_itens("falta areia, 4 m³ de areia média")[0]) == ("areia media", 4, "m3")
    assert chave_item(m.extrair_itens("urgente 200 tijolos 6 furos")[0]) == ("tijolo 6 furo", 200, "un")


def test_extracao_v1_erra_onde_o_eval_apontou():
    # é o motivo de a v2 existir: a v1 não conhece "m³" nem contáveis sem unidade
    assert chave_item(ModeloRegras(1).extrair_itens("falta areia, 4 m³ de areia média")[0])[2] is None
    assert ModeloRegras(1).extrair_itens("urgente 200 tijolos 6 furos")[0]["unidade"] is None


def test_numero_dentro_da_descricao_nao_vira_item():
    itens = ModeloRegras(2).extrair_itens("manda 10 barras de vergalhão 10mm")
    assert len(itens) == 1 and itens[0]["quantidade"] == 10


def test_duvida_tecnica_nunca_e_respondida_pelo_agente():
    resposta = ModeloRegras(2).responder_duvida("qual o traço do concreto?")
    assert "engenheiro" in resposta and "traço" not in resposta.lower().replace("sua pergunta", "")


def test_faq_nao_tecnica_responde():
    assert "7h às 16h" in ModeloRegras(2).responder_duvida("qual o horário de entrega do material?")
