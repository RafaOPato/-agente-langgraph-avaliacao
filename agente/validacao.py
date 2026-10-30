"""Validação determinística dos itens extraídos. Fica no código, não no modelo: regra que não pode falhar."""
from .normaliza import normalizar_unidade

LIMITE_QUANTIDADE = 500
UNIDADES_ACEITAS = {"saco", "lata", "rolo", "barra", "kg", "m3", "caixa", "balde", "un", "litro"}


def validar(itens: list[dict]) -> list[str]:
    if not itens:
        return ["Não entendi nenhum item no pedido."]
    erros = []
    for item in itens:
        nome = item.get("descricao", "?")
        quantidade = item.get("quantidade")
        unidade = normalizar_unidade(item.get("unidade"))
        if quantidade is None or quantidade <= 0:
            erros.append(f"{nome}: quantidade inválida.")
        elif quantidade > LIMITE_QUANTIDADE:
            erros.append(f"{nome}: quantidade {quantidade} acima do limite de {LIMITE_QUANTIDADE}; confirmar com o engenheiro.")
        if unidade is None:
            erros.append(f"{nome}: informe a unidade (saco, lata, kg...).")
        elif unidade not in UNIDADES_ACEITAS:
            erros.append(f"{nome}: unidade '{unidade}' não reconhecida.")
    return erros
