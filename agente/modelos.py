"""O "modelo" que o grafo usa.

Aqui o modelo é um conjunto de regras (palavras-chave e expressões regulares), determinístico, de propósito:
o projeto roda e é testável sem chave e sem custo, e o foco é o grafo e a avaliação. Para trocar por um LLM
basta outra classe com os mesmos três métodos (`classificar`, `extrair_itens`, `responder_duvida`); eu não
fiz essa troca (ver README, Limitações).

`ModeloRegras(versao=1)` é a primeira tentativa, simples. `versao=2` incorpora o que o eval mostrou que
faltava nos casos de desenvolvimento (split "dev").
"""
import re
from typing import Protocol

from .normaliza import normalizar_descricao

CATEGORIAS = ("pedido_compra", "duvida_tecnica", "cobranca", "outro")

# Contáveis sem unidade escrita: "200 tijolos" -> unidade "un". Só a versão 2 conhece essa lista.
CONTAVEIS = ("tijolo", "pincel", "telha", "bloco", "parafuso", "prego", "luva", "registro", "torneira")

_PEDIDO_V1 = ("preciso", "manda", "mande", "compra", "comprar", "falta", "vou precisar", "urgente")
_COBRANCA_V1 = ("cobra", "cobrar")
_COBRANCA_V2 = _COBRANCA_V1 + ("atrasou", "atraso", "não entregou", "nao entregou", "ainda não chegou", "ninguém respondeu", "sem resposta")
_INTERROGATIVAS = ("qual ", "como ", "quanto ", "quantos ", "quando ")

_UNIDADES_V1 = r"sacos?|latas?|rolos?|barras?|kg|caixas?|unidades?|un"
_UNIDADES_V2 = _UNIDADES_V1 + r"|baldes?|m3|m³|quilos?|litros?"
_CORTES_V2 = (" pra ", " para ", " até ", " ate ", " hoje", " urgente")

# FAQ não técnica (fictícia). Dúvida técnica NUNCA é respondida pelo agente: vai para o engenheiro.
FAQ = {
    "horário de entrega": "A portaria da obra recebe material das 7h às 16h (exemplo fictício).",
    "onde descarrega": "A descarga é feita pelo portão lateral (exemplo fictício).",
}


class Modelo(Protocol):
    def classificar(self, mensagem: str) -> str: ...
    def extrair_itens(self, mensagem: str) -> list[dict]: ...
    def responder_duvida(self, mensagem: str) -> str: ...


class ModeloRegras:
    def __init__(self, versao: int = 2):
        if versao not in (1, 2):
            raise ValueError("versao deve ser 1 ou 2")
        self.versao = versao

    # ---- classificação ----
    def classificar(self, mensagem: str) -> str:
        texto = mensagem.lower()
        cobranca = _COBRANCA_V2 if self.versao == 2 else _COBRANCA_V1
        if any(p in texto for p in cobranca):
            return "cobranca"
        tem_numero = re.search(r"\d", texto) is not None
        if any(p in texto for p in _PEDIDO_V1) and (tem_numero or self.versao == 1):
            return "pedido_compra"
        if "?" in texto or any(texto.startswith(p) or f" {p}" in texto for p in _INTERROGATIVAS):
            return "duvida_tecnica"
        return "outro"

    # ---- extração ----
    def extrair_itens(self, mensagem: str) -> list[dict]:
        unidades = _UNIDADES_V2 if self.versao == 2 else _UNIDADES_V1
        padrao = re.compile(
            rf"(?<![\w-])(?P<qtd>\d+(?:[.,]\d+)?)\s+(?:(?P<un>{unidades})\b\s*)?(?:de\s+)?(?P<desc>.+)$",
            re.IGNORECASE,
        )
        itens = []
        for segmento in re.split(r",|\.\s|;|\se\s", mensagem):
            achado = padrao.search(segmento.strip())
            if not achado:
                continue
            descricao = achado.group("desc").strip()
            if self.versao == 2:
                for corte in _CORTES_V2:
                    posicao = (" " + descricao.lower()).find(corte)
                    if posicao >= 0:
                        descricao = descricao[: max(posicao - 1, 0)].strip()
            unidade = achado.group("un")
            unidade = unidade.lower() if unidade else None
            if unidade is None and self.versao == 2 and any(normalizar_descricao(descricao).startswith(c) for c in CONTAVEIS):
                unidade = "un"
            quantidade = float(achado.group("qtd").replace(",", "."))
            itens.append({
                "descricao": descricao,
                "quantidade": int(quantidade) if quantidade.is_integer() else quantidade,
                "unidade": unidade,
            })
        return itens

    # ---- dúvida ----
    def responder_duvida(self, mensagem: str) -> str:
        texto = mensagem.lower()
        for gatilho, resposta in FAQ.items():
            if gatilho in texto:
                return resposta
        return "Não respondo dúvida técnica: encaminhei sua pergunta ao engenheiro responsável."
