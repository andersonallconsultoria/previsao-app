"""
Montagem da DRE a partir dos dados brutos do endpoint centro_resultado_bi.

Recebe a lista de itens já consultada (mesma fonte do painel) e devolve
uma estrutura pronta para o template renderizar: lista de linhas (grupos,
sections e subtotais) e, para cada linha, valores por mês × {ano_anterior,
previsto, realizado} mais o total anual.
"""

from collections import defaultdict
from .dre_config import get_estrutura_dre, classificar_conta


def _mes_str(mes_raw):
    """Converte mesNum em string 'MM' zero-padded. Retorna None se inválido."""
    if mes_raw is None:
        return None
    try:
        return str(int(mes_raw)).zfill(2)
    except (ValueError, TypeError):
        return None


def _meses_do_periodo(dt_ini, dt_fim):
    """Lista de meses 'MM' entre as datas (inclusive). Espera datetime.date/datetime."""
    if dt_ini is None or dt_fim is None:
        return [f"{m:02d}" for m in range(1, 13)]
    if dt_ini > dt_fim:
        dt_ini, dt_fim = dt_fim, dt_ini
    ano = dt_ini.year
    mes_ini = dt_ini.month if dt_ini.year == ano else 1
    mes_fim = dt_fim.month if dt_fim.year == ano else 12
    return [f"{m:02d}" for m in range(mes_ini, mes_fim + 1)]


def _zera_meses(meses):
    return {m: {"ano_anterior": 0.0, "previsto": 0.0, "realizado": 0.0} for m in meses}


def montar_dre(dados, meses, estrutura=None):
    """
    Args:
        dados: lista de itens vinda de centro_resultado_bi (cada item tem
               'contabil', 'mesNum', 'anoAnterior', 'valorPrevisto', 'valorRealizado').
        meses: lista de strings 'MM' que devem aparecer na DRE.
        estrutura: estrutura DRE (default = get_estrutura_dre()).

    Returns:
        dict com chaves:
          - 'linhas': lista de dicts {tipo, label, id?, valores: {mm:{ano_anterior,previsto,realizado}}, totais: {ano_anterior,previsto,realizado}, destacar?, total?}
          - 'meses': meses solicitados
          - 'contas_sem_classificacao': lista de contas que não casaram com nenhum grupo (debug)
    """
    estrutura = estrutura or get_estrutura_dre()

    # Acumulador: grupo_id -> mes -> {ano_anterior, previsto, realizado}
    acumulador = defaultdict(lambda: _zera_meses(meses))
    contas_sem_classificacao = set()

    for item in dados:
        contabil = item.get("contabil")
        mes = _mes_str(item.get("mesNum"))
        if not contabil or mes is None or mes not in meses:
            continue

        grupo_id = classificar_conta(contabil, estrutura)
        if grupo_id is None:
            contas_sem_classificacao.add(str(contabil))
            continue

        ano_ant = float(item.get("anoAnterior") or 0)
        previsto = float(item.get("valorPrevisto") or 0)
        realizado = float(item.get("valorRealizado") or 0)

        acumulador[grupo_id][mes]["ano_anterior"] += ano_ant
        acumulador[grupo_id][mes]["previsto"] += previsto
        acumulador[grupo_id][mes]["realizado"] += realizado

    # Subtotais: aplicam fórmulas referenciando outros ids (grupos ou subtotais já calculados)
    def _aplicar_formula(formula, mes):
        agg = {"ano_anterior": 0.0, "previsto": 0.0, "realizado": 0.0}
        for token in formula:
            sinal = -1.0 if token.startswith("-") else 1.0
            ref_id = token[1:] if token.startswith("-") else token
            ref = acumulador.get(ref_id, {}).get(mes)
            if not ref:
                continue
            for k in agg:
                agg[k] += sinal * ref[k]
        return agg

    for linha in estrutura:
        if linha.get("tipo") != "subtotal":
            continue
        sid = linha["id"]
        if sid in acumulador:
            continue  # já foi populado (não deveria, mas é defesa)
        for mes in meses:
            acumulador[sid][mes] = _aplicar_formula(linha["formula"], mes)

    # Monta o output: percorre estrutura preservando ordem
    linhas_out = []
    for linha in estrutura:
        tipo = linha.get("tipo")
        if tipo == "section":
            linhas_out.append({"tipo": "section", "label": linha["label"]})
            continue

        sid = linha["id"]
        valores = acumulador.get(sid, _zera_meses(meses))
        totais = {"ano_anterior": 0.0, "previsto": 0.0, "realizado": 0.0}
        for mes in meses:
            for k in totais:
                totais[k] += valores[mes][k]

        linhas_out.append({
            "tipo": tipo,
            "id": sid,
            "label": linha["label"],
            "valores": valores,
            "totais": totais,
            "destacar": linha.get("destacar", False),
            "total": linha.get("total", False),
        })

    return {
        "linhas": linhas_out,
        "meses": meses,
        "contas_sem_classificacao": sorted(contas_sem_classificacao),
    }


def gerar_dados_mock(meses, ano):
    """Gera dataset fake (mesmo formato de centro_resultado_bi) para testar a tela
    enquanto o serviço real não está plugado.

    Cria registros para um conjunto de contas contábeis cobrindo todos os
    prefixos da estrutura padrão, com variação sazonal e ruído.
    """
    import math
    import random
    from .dre_config import get_estrutura_dre

    rng = random.Random(int(ano) * 100 + 42)
    estrutura = get_estrutura_dre()

    # Para cada classificação, inventa 1-2 contas filhas (sufixos)
    contas_por_grupo = []
    for linha in estrutura:
        if linha.get("tipo") != "grupo":
            continue
        for classif in linha.get("classificacoes", []):
            base = str(classif)
            # 2 sub-contas por classificação
            contas_por_grupo.append((linha["id"], f"{base}01"))
            contas_por_grupo.append((linha["id"], f"{base}02"))

    # Magnitude base por grupo (valor mensal típico em R$)
    magnitudes = {
        "receita_bruta": 7_200_000,
        "deducoes": 350_000,
        "custo_operacional": 4_400_000,
        "despesas_operacionais": 750_000,
        "outras_despesas": 180_000,
        "outras_receitas_op": 90_000,
        "receitas_financeiras": 40_000,
        "provisao_contribuicao": 60_000,
        "provisao_ir": 110_000,
    }

    dados = []
    for idx, mes in enumerate(meses):
        mes_int = int(mes)
        sazonal = 1.0 + 0.10 * math.sin((idx / 12.0) * math.pi * 2)
        for grupo_id, conta in contas_por_grupo:
            base = magnitudes.get(grupo_id, 50_000) / 2.0  # 2 contas por classif
            ruido_prev = rng.uniform(0.85, 1.15)
            previsto = base * sazonal * ruido_prev
            realizado = previsto * rng.uniform(0.88, 1.18)
            ano_anterior = previsto * rng.uniform(0.85, 1.10)
            dados.append({
                "contabil": conta,
                "mesNum": mes_int,
                "anoreferencia": int(ano),
                "anoAnterior": round(ano_anterior, 2),
                "valorPrevisto": round(previsto, 2),
                "valorRealizado": round(realizado, 2),
            })

    return dados
