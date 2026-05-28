"""
Configuração padrão da estrutura DRE.

A estrutura abaixo replica a configuração do sistema CISS-Poder
("Classificações Contábeis para Gerar DRE"). Cada grupo agrega uma ou mais
classificações contábeis (match por PREFIXO sobre o campo `contabil`).

Quando o serviço externo que retorna a configuração estiver disponível,
substituir `get_estrutura_dre()` por uma chamada HTTP que retorne o mesmo
formato.
"""

# Tipo de linha:
#   "grupo"    -> linha que agrega contas (entra no cálculo de subtotais)
#   "section"  -> cabeçalho de seção visual (não calcula)
#   "subtotal" -> subtotal calculado (id referenciado em SUBTOTAIS_DRE)
#
# Sinal:
#   "+" soma no acumulador da seção em que entra
#   "-" subtrai (ex: deduções, custos, despesas)
#
# Cada item de `classificacoes` é casado por PREFIXO contra `item["contabil"]`.

ESTRUTURA_DRE_PADRAO = [
    {"tipo": "section", "label": "RECEITA OPERACIONAL"},
    {"tipo": "grupo", "id": "receita_bruta", "label": "Receita Operacional Bruta",
     "sinal": "+", "classificacoes": ["31101"]},
    {"tipo": "grupo", "id": "deducoes", "label": "(-) Deduções e Abatimentos",
     "sinal": "-", "classificacoes": ["31103", "31102"]},
    {"tipo": "subtotal", "id": "vendas_brutas", "label": "(=) Vendas Brutas",
     "formula": ["receita_bruta", "-deducoes"]},

    {"tipo": "section", "label": "CUSTOS"},
    {"tipo": "grupo", "id": "custo_operacional", "label": "(-) Custo Operacional",
     "sinal": "-", "classificacoes": ["41102", "41101"]},
    {"tipo": "subtotal", "id": "lucro_bruto", "label": "(=) Lucro Bruto", "destacar": True,
     "formula": ["vendas_brutas", "-custo_operacional"]},

    {"tipo": "section", "label": "DESPESAS OPERACIONAIS"},
    {"tipo": "grupo", "id": "despesas_operacionais", "label": "(-) Despesas Operacionais",
     "sinal": "-", "classificacoes": ["421"]},
    {"tipo": "grupo", "id": "outras_despesas", "label": "(-) Outras Despesas",
     "sinal": "-", "classificacoes": ["42203", "422"]},
    {"tipo": "subtotal", "id": "total_despesas_op", "label": "(=) Total Despesas Operacionais",
     "destacar": True, "formula": ["despesas_operacionais", "outras_despesas"]},

    {"tipo": "section", "label": "OUTRAS RECEITAS E DESPESAS"},
    {"tipo": "grupo", "id": "outras_receitas_op", "label": "(+) Outras Receitas Operacionais",
     "sinal": "+", "classificacoes": ["312"]},
    {"tipo": "grupo", "id": "receitas_financeiras", "label": "(+) Receitas Financeiras",
     "sinal": "+", "classificacoes": ["321"]},

    {"tipo": "section", "label": "PROVISÕES"},
    {"tipo": "grupo", "id": "provisao_contribuicao", "label": "(-) Provisão para Contribuição",
     "sinal": "-", "classificacoes": ["431010002"]},
    {"tipo": "grupo", "id": "provisao_ir", "label": "(-) Provisão para Imposto de Renda",
     "sinal": "-", "classificacoes": ["431010003", "431010001"]},

    {"tipo": "section", "label": "RESULTADO"},
    {"tipo": "subtotal", "id": "resultado", "label": "(=) RESULTADO DO PERÍODO",
     "destacar": True, "total": True,
     "formula": [
         "lucro_bruto",
         "-total_despesas_op",
         "outras_receitas_op",
         "receitas_financeiras",
         "-provisao_contribuicao",
         "-provisao_ir",
     ]},
]


def get_estrutura_dre():
    """Retorna a estrutura DRE atual.

    Hoje devolve o mock acima. Quando o serviço externo estiver disponível,
    trocar esta função pela chamada HTTP que retorna o mesmo shape.
    """
    return ESTRUTURA_DRE_PADRAO


def classificar_conta(contabil, estrutura=None):
    """Dado um código contábil, retorna o id do grupo DRE em que ele se encaixa.

    Match por PREFIXO: a classificação configurada é prefixo da conta contábil.
    Em caso de múltiplos matches, vence o prefixo mais longo (mais específico).
    Retorna None se a conta não pertence a nenhum grupo da DRE.
    """
    if contabil is None:
        return None
    contabil_str = str(contabil).strip()
    if not contabil_str:
        return None

    estrutura = estrutura or get_estrutura_dre()

    melhor_id = None
    melhor_prefixo_len = -1
    for linha in estrutura:
        if linha.get("tipo") != "grupo":
            continue
        for classif in linha.get("classificacoes", []):
            prefixo = str(classif).strip()
            if not prefixo:
                continue
            if contabil_str.startswith(prefixo) and len(prefixo) > melhor_prefixo_len:
                melhor_id = linha["id"]
                melhor_prefixo_len = len(prefixo)

    return melhor_id


def grupos_da_estrutura(estrutura=None):
    """Lista apenas os grupos (linhas que somam valores)."""
    estrutura = estrutura or get_estrutura_dre()
    return [l for l in estrutura if l.get("tipo") == "grupo"]
