"""
Camada de acesso aos endpoints CISS-Poder relacionados a liberação de excedente.

Endpoints expostos no CISS-Poder:
  - /liberacao_listar_pendentes  (SELECT)   -> tela "Aprovar Liberações"
  - /liberacao_listar_minhas     (SELECT)   -> tela "Minhas Solicitações"
  - /liberacao_count_pendentes   (SELECT)   -> badge no menu
  - /liberacao_decidir           (FUNCTION) -> aprovar/recusar

Todas as chamadas usam o service account (get_api_headers()) — controle de
permissão acontece no Django via usuarios_config.json.
"""

import requests
import logging

from . import views as _v  # reaproveita get_dynamic_config, get_api_headers

logger = logging.getLogger(__name__)


def _post_endpoint(endpoint, payload, timeout=30):
    """Wrapper centralizado pra POSTs aos endpoints CISS-Poder.

    Para endpoints SELECT, payload é dict com page/limit/clausulas.
    Para endpoints FUNCTION/PROCEDURE, payload é list de dict com chaves UPPERCASE.
    """
    url = f"{_v.get_dynamic_config('API_BASE_URL')}/cisspoder-service/{endpoint}"
    try:
        resp = requests.post(url, json=payload, headers=_v.get_api_headers(), timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"⚠️ {endpoint} retornou {resp.status_code}: {resp.text[:200]}")
        return {"data": [], "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.exception(f"❌ Erro ao chamar {endpoint}")
        return {"data": [], "error": str(e)}


def listar_pendentes(page=1, limit=100):
    """Lista todas as solicitações pendentes (para o aprovador)."""
    payload = {"page": page, "limit": limit, "clausulas": []}
    resp = _post_endpoint("liberacao_listar_pendentes", payload)
    return resp.get("data", [])


def listar_minhas(userso, page=1, limit=100):
    """Lista as solicitações do usuário logado (qualquer status)."""
    payload = {
        "page": page,
        "limit": limit,
        "clausulas": [
            {"campo": "userso", "operadorlogico": "AND", "operador": "IGUAL", "valor": userso},
        ],
    }
    resp = _post_endpoint("liberacao_listar_minhas", payload)
    return resp.get("data", [])


def count_pendentes():
    """Retorna a contagem de solicitações pendentes (para o badge)."""
    resp = _post_endpoint("liberacao_count_pendentes", {"page": 1, "limit": 1, "clausulas": []}, timeout=10)
    data = resp.get("data", [])
    if data and isinstance(data, list) and len(data) > 0:
        # A API pode retornar com key TOTAL_PENDENTES ou totalPendentes (camelCase)
        first = data[0]
        return int(first.get("TOTAL_PENDENTES") or first.get("totalPendentes") or 0)
    return 0


def decidir(idsolicitacao, decisao, tipo_liberacao, valor_extra, perc_extra,
            usuario_aprovador, observacao):
    """Aprova ou recusa uma solicitação.

    Args:
        idsolicitacao: int — ID da solicitação
        decisao: 'A' (aprovar) ou 'R' (recusar)
        tipo_liberacao: 'U', 'V' ou 'P' (só usado se decisao='A'; senão None)
        valor_extra: decimal — só usado se tipo='V'; senão None
        perc_extra: decimal — só usado se tipo='P'; senão None
        usuario_aprovador: username (string)
        observacao: texto (obrigatório, validado também no banco)

    Returns:
        dict com 'success' (bool) e 'message' (str).
    """
    # Endpoints FUNCTION/PROCEDURE no CISS-Poder esperam array de objetos com
    # chaves em UPPERCASE (mesmo padrao do /set_centroresultado_config).
    payload = [{
        "P_IDSOLICITACAO":     int(idsolicitacao),
        "P_DECISAO":           decisao,
        "P_TIPO":              tipo_liberacao,
        "P_VALOR_EXTRA":       valor_extra,
        "P_PERC_EXTRA":        perc_extra,
        "P_USUARIO_APROVADOR": usuario_aprovador,
        "P_OBSERVACAO":        observacao,
    }]
    resp = _post_endpoint("liberacao_decidir", payload, timeout=30)
    return _parse_mensagem_ok_erro(resp)


def criar(idempresa, idcentroresultado, idctacontabil, dtmovimento,
          vallancamento, justificativa, idusuario, userso):
    """Cria uma solicitação manual (antes do operador tentar lançar).

    Args:
        idempresa, idcentroresultado, idctacontabil: ints
        dtmovimento: string 'YYYY-MM-DD'
        vallancamento: float (valor positivo)
        justificativa: string (obrigatória)
        idusuario: int ou None (ID interno do CISS-Poder; pode ser None)
        userso: string (username, ex: 'ANDERSON.SANTOS') — obrigatório

    Returns:
        dict {'success': bool, 'message': str}
    """
    payload = [{
        "P_IDEMPRESA":         int(idempresa),
        "P_IDCENTRORESULTADO": int(idcentroresultado),
        "P_IDCTACONTABIL":     int(idctacontabil),
        "P_DTMOVIMENTO":       dtmovimento,
        "P_VALLANCAMENTO":     float(vallancamento),
        "P_JUSTIFICATIVA":     justificativa,
        "P_IDUSUARIO":         int(idusuario) if idusuario else None,
        "P_USERSO":            userso,
    }]
    resp = _post_endpoint("liberacao_criar", payload, timeout=30)
    return _parse_mensagem_ok_erro(resp)


def _parse_mensagem_ok_erro(resp):
    """Parser comum para functions que retornam MENSAGEM com prefixo OK:/ERRO:."""
    data = resp.get("data", [])
    if not data:
        return {"success": False, "message": resp.get("error") or "Resposta vazia do servidor"}
    first = data[0]
    mensagem = (first.get("MENSAGEM") or first.get("mensagem") or "").strip()
    if not mensagem:
        return {"success": False, "message": "Sem mensagem na resposta"}
    upper = mensagem.upper()
    success = upper.startswith("OK")
    msg_limpa = mensagem.split(":", 1)[1].strip() if ":" in mensagem else mensagem
    return {"success": success, "message": msg_limpa}
