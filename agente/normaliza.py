"""Normalização de texto e de itens, para comparar o que o agente entendeu com o que era esperado."""
import re
import unicodedata

STOPWORDS = {"de", "da", "do", "das", "dos", "para", "pra", "e"}

UNIDADES = {
    "saco": "saco", "sacos": "saco", "lata": "lata", "latas": "lata", "rolo": "rolo", "rolos": "rolo",
    "barra": "barra", "barras": "barra", "kg": "kg", "quilo": "kg", "quilos": "kg",
    "m3": "m3", "m³": "m3", "caixa": "caixa", "caixas": "caixa", "balde": "balde", "baldes": "balde",
    "un": "un", "unidade": "un", "unidades": "un", "litro": "litro", "litros": "litro",
}


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def _singular(palavra: str) -> str:
    if palavra.endswith("eis") and len(palavra) > 4:
        return palavra[:-3] + "el"  # pincéis -> pincel
    if len(palavra) > 3 and palavra.endswith("s") and not palavra.endswith("ss"):
        return palavra[:-1]
    return palavra


def normalizar_descricao(texto: str) -> str:
    palavras = re.findall(r"[a-z0-9\-]+", sem_acento(texto.lower()))
    return " ".join(_singular(p) for p in palavras if p not in STOPWORDS)


def normalizar_unidade(unidade):
    if unidade is None:
        return None
    chave = unidade.lower().strip()
    return UNIDADES.get(chave, UNIDADES.get(sem_acento(chave), chave))


def chave_item(item: dict) -> tuple:
    """Identidade de um item para comparação: descrição normalizada, quantidade e unidade normalizada."""
    quantidade = item.get("quantidade")
    if isinstance(quantidade, float) and quantidade.is_integer():
        quantidade = int(quantidade)
    return (normalizar_descricao(item.get("descricao", "")), quantidade, normalizar_unidade(item.get("unidade")))
