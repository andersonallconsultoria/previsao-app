from django.shortcuts import render, redirect
from django.http import JsonResponse
import requests
from decouple import config
from .decorators import token_required
from collections import defaultdict
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Filtro de template
from django.template.defaulttags import register
@register.filter
def get_item(dictionary, key):
    return dictionary.get(str(key), {})

# Função auxiliar para logs JSON bonitos
def log_json_pretty(obj, title=None):
    if title:
        logger.info(f"{title}\n{json.dumps(obj, indent=2, ensure_ascii=False)}")
    else:
        logger.info(json.dumps(obj, indent=2, ensure_ascii=False))

# Token OAuth2
def gerar_token(username, password):
    url = f"{config('API_BASE_URL')}/cisspoder-auth/oauth/token"
    payload = {
        'username': username,
        'password': password,
        'grant_type': 'password',
        'client_id': config('CLIENT_ID'),
        'client_secret': config('CLIENT_SECRET'),
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(url, data=payload, headers=headers)
    return response.json()

# Login
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        token_data = gerar_token(username, password)
        if 'access_token' in token_data:
            request.session['token'] = token_data['access_token']
            return redirect('painel')
        else:
            return render(request, 'login.html', {'erro': 'Login inválido'})
    return render(request, 'login.html')

# Painel principal
@token_required
def painel_view(request):
    token = request.session['token']
    headers = {
        'Authorization': f"Bearer {token}",
        'Content-Type': 'application/json'
    }

    ano_atual = datetime.now().year

    def post_api(endpoint):
        url = f"{config('API_BASE_URL')}/cisspoder-service/{endpoint}"
        try:
            resp = requests.post(url, json={"page": 1}, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("data", [])
            else:
                logger.warning(f"⚠️ {endpoint} retornou {resp.status_code}")
        except Exception as e:
            logger.exception(f"❌ Erro ao buscar {endpoint}")
        return []

    empresas = post_api('cadastro_empresa')
    centros = post_api('cadastro_centroresultados')
    resultados = []
    agrupado = {}
    meses_lista = [(f"{i:02d}", f"{i:02d}") for i in range(1, 13)]

    if request.method == 'POST':
        ano = int(request.POST.get("ano", 2025))
        empresa = request.POST.get("empresa") or None
        centro = request.POST.get("centro") or None

        logger.info(f"🔎 Filtros aplicados: ano={ano}, empresa={empresa}, centro={centro}")

        payload = {
            "page": 1,
            "limit": 1000,
            "clausulas": [
                {"campo": "anoreferencia", "operadorlogico": "AND", "operador": "IGUAL", "valor": ano}
            ]
        }

        if empresa:
            try:
                emp_int = int(empresa)
                payload["clausulas"].append({
                    "campo": "idempfiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": emp_int
                })
            except ValueError:
                logger.warning(f"⚠️ Empresa inválida: {empresa}")

        # Sempre adicionar a cláusula de centro de resultados
        if centro and centro.strip():
            try:
                centro_int = int(centro)
                payload["clausulas"].append({
                    "campo": "idcentroresultadofiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": centro_int
                })
                # Se centro específico foi selecionado, não agrupar por centro
                agrupar_por_centro = False
                logger.info(f"🎯 Centro específico selecionado: {centro_int}")
            except ValueError:
                logger.warning(f"⚠️ Centro inválido: {centro}")
                # Se centro inválido, enviar null
                payload["clausulas"].append({
                    "campo": "idcentroresultadofiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": None
                })
                agrupar_por_centro = True
                logger.info("🔄 Centro inválido - enviando null")
        else:
            # Se centro estiver vazio ou for "Todos", enviar null
            payload["clausulas"].append({
                "campo": "idcentroresultadofiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": None
            })
            logger.info("🏢 Filtro de centro: 'Todos' selecionado - enviando null")
            agrupar_por_centro = True

        logger.info(f"📤 Enviando payload para /centro_resultado_bi:")
        logger.info(f"🔍 Filtros aplicados:")
        logger.info(f"   - Ano: {ano}")
        logger.info(f"   - Empresa: {empresa if empresa else 'Todas'}")
        logger.info(f"   - Centro: {centro if centro and centro.strip() else 'Todos (null)'}")
        logger.info(f"   - Agrupar por centro: {agrupar_por_centro}")
        log_json_pretty(payload)

        url = f"{config('API_BASE_URL')}/cisspoder-service/centro_resultado_bi"
        try:
            # Implementar paginação para buscar todas as páginas
            resultados = []
            page = 1
            total_registros = 0
            
            while True:
                payload["page"] = page
                logger.info(f"📄 Buscando página {page}...")
                
                resp = requests.post(url, json=payload, headers=headers)
                logger.info(f"📥 Status da requisição (página {page}): {resp.status_code}")
                
                if resp.status_code == 200:
                    response_data = resp.json()
                    page_data = response_data.get("data", [])
                    total_registros = response_data.get("total", 0)
                    has_next = response_data.get("hasNext", False)
                    
                    resultados.extend(page_data)
                    logger.info(f"✅ Página {page}: {len(page_data)} registros recebidos")
                    logger.info(f"📊 Total acumulado: {len(resultados)} de {total_registros}")
                    
                    if not has_next:
                        logger.info(f"🏁 Última página alcançada: {page}")
                        break
                    
                    page += 1
                else:
                    logger.warning(f"⚠️ Erro na página {page}: {resp.text}")
                    break
            
            request.session['resultados_debug'] = resultados
            logger.info(f"✅ Total final de registros: {len(resultados)}")
            log_json_pretty(resultados[:3], "📊 Primeiros resultados:")

            resultado_agrupado = agrupar_resultados(resultados, agrupar_por_centro)
                
            if agrupar_por_centro:
                agrupado_por_centro = resultado_agrupado['agrupado_por_centro']
                totalizadores_centro = resultado_agrupado['totalizadores_centro']
                agrupado = {}  # Não usado quando agrupado por centro
                
                for centro, contas in agrupado_por_centro.items():
                    for conta, meses in contas.items():
                        for mes, valores in meses.items():
                            logger.info(f"📌 Centro: {centro} | Conta: {conta} | Mês: {mes} | Dados: {valores}")
                
                logger.info(f"📦 Total de centros agrupados: {len(agrupado_por_centro)}")
                logger.info(f"📦 Totalizadores por centro: {len(totalizadores_centro)}")
                log_json_pretty(list(agrupado_por_centro.keys())[:5], "🔑 Centros agrupados:")
            else:
                agrupado = resultado_agrupado['agrupado']
                totalizadores_centro = resultado_agrupado['totalizadores_centro']
                totais_anuais_conta = resultado_agrupado.get('totais_anuais_conta', {})
                agrupado_por_centro = {}  # Não usado quando agrupado por conta
                
                for conta, meses in agrupado.items():
                    for mes, valores in meses.items():
                        logger.info(f"📌 Conta: {conta} | Mês: {mes} | Dados: {valores}")
                
                logger.info(f"📦 Total de contas agrupadas: {len(agrupado)}")
                logger.info(f"📦 Totalizadores por centro: {len(totalizadores_centro)}")
                log_json_pretty(list(agrupado.keys())[:5], "🔑 Contas agrupadas:")
            
            log_json_pretty(totalizadores_centro, "💰 Totalizadores por centro:")
        except Exception:
            logger.exception("❌ Erro na requisição ao endpoint /centro_resultado_bi")
            

    return render(request, 'painel.html', {
        'empresas': empresas,
        'centros': centros,
        'resultados': resultados,
        'agrupado': agrupado if 'agrupado' in locals() else {},
        'agrupado_por_centro': agrupado_por_centro if 'agrupado_por_centro' in locals() else {},
        'totalizadores_centro': totalizadores_centro if 'totalizadores_centro' in locals() else {},
        'totais_anuais_conta': totais_anuais_conta if 'totais_anuais_conta' in locals() else {},
        'agrupar_por_centro': agrupar_por_centro if 'agrupar_por_centro' in locals() else False,
        'meses': meses_lista,
        'ano_atual': ano_atual,
    })

# Agrupamento dos dados por conta e mês com totalizadores por centro de resultados
def agrupar_resultados(dados, agrupar_por_centro=False):
    from collections import defaultdict

    if agrupar_por_centro:
        # Agrupamento por centro de resultados e depois por conta
        agrupado_por_centro = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        totalizadores_centro = defaultdict(lambda: defaultdict(float))
    else:
        # Agrupamento tradicional por conta
        agrupado = defaultdict(lambda: defaultdict(dict))
        totalizadores_centro = defaultdict(lambda: defaultdict(float))
        totais_anuais_conta = defaultdict(lambda: defaultdict(float))

    for item in dados:
        conta = item.get("contabil")
        mes_raw = item.get("mesNum")
        # Tentar diferentes campos possíveis para centro de resultados
        centro_resultado = (
            item.get("centroresultados") or 
            item.get("centroResultados") or 
            item.get("centro_resultados") or 
            item.get("centro") or 
            item.get("centroResultado") or 
            item.get("descrcentroresultado") or  # Adicionar este campo
            item.get("CENTRO_RESULTADOS") or  # Campo da função DB2
            "Sem Centro"
        )

        # Validação dos dados obrigatórios
        if not conta:
            logger.warning(f"⚠️ Conta contábil ausente no item: {item}")
            continue

        if mes_raw is None:
            logger.warning(f"⚠️ Mês de referência ausente no item: {item}")
            continue

        try:
            mes = str(int(mes_raw)).zfill(2)  # Garantir que seja string "01", "02", ..., "12"
        except Exception:
            logger.exception(f"❌ Erro ao processar o mês: {mes_raw}")
            continue

        try:
            ano_anterior = item.get("anoAnterior", 0)
            previsto = item.get("valorPrevisto", 0)
            realizado = item.get("valorRealizado", 0)

            if agrupar_por_centro:
                # Agrupar por centro de resultados primeiro
                agrupado_por_centro[centro_resultado][conta][mes] = {
                    'ano_anterior': ano_anterior,
                    'previsto': previsto,
                    'realizado': realizado
                }
            else:
                # Agrupamento tradicional
                agrupado[conta][mes] = {
                    'ano_anterior': ano_anterior,
                    'previsto': previsto,
                    'realizado': realizado,
                    'centro_resultado': centro_resultado
                }

            # Acumular totalizadores por centro de resultados
            totalizadores_centro[centro_resultado][f"{mes}_ano_anterior"] += ano_anterior
            totalizadores_centro[centro_resultado][f"{mes}_previsto"] += previsto
            totalizadores_centro[centro_resultado][f"{mes}_realizado"] += realizado
            
            # Acumular totais anuais
            totalizadores_centro[centro_resultado]["ano_anterior_total"] += ano_anterior
            totalizadores_centro[centro_resultado]["previsto_total"] += previsto
            totalizadores_centro[centro_resultado]["realizado_total"] += realizado
            
            # Acumular totais anuais por conta (quando não agrupado por centro)
            if not agrupar_por_centro:
                totais_anuais_conta[conta]["ano_anterior_total"] += ano_anterior
                totais_anuais_conta[conta]["previsto_total"] += previsto
                totais_anuais_conta[conta]["realizado_total"] += realizado

            # Log para debug da estrutura dos dados
            if len(agrupado) <= 3 if not agrupar_por_centro else len(agrupado_por_centro) <= 3:
                logger.debug(f"🔍 Item processado - Conta: {conta}, Centro: {centro_resultado}, Mês: {mes}")
                logger.debug(f"🔍 Chaves disponíveis no item: {list(item.keys())}")
                logger.debug(f"🔍 Campo centro_resultado encontrado: {centro_resultado}")
                logger.debug(f"🔍 Campo descrcentroresultado: {item.get('descrcentroresultado')}")
                logger.debug(f"🔍 Campo centroresultados: {item.get('centroresultados')}")

        except Exception:
            logger.exception(f"❌ Erro ao agrupar dados para conta {conta} e mês {mes}")

    # Função para converter defaultdict em dict recursivamente
    def to_dict(d):
        if isinstance(d, defaultdict):
            d = {k: to_dict(v) for k, v in d.items()}
        return d

    if agrupar_por_centro:
        logger.info(f"📦 Total de centros agrupados: {len(agrupado_por_centro)}")
        return {
            'agrupado_por_centro': to_dict(agrupado_por_centro),
            'totalizadores_centro': to_dict(totalizadores_centro)
        }
    else:
        logger.info(f"📦 Total de contas agrupadas: {len(agrupado)}")
        return {
            'agrupado': to_dict(agrupado),
            'totalizadores_centro': to_dict(totalizadores_centro),
            'totais_anuais_conta': to_dict(totais_anuais_conta)
        }

# Tela de debug
@token_required
def debug_resultados_view(request):
    resultados = request.session.get('resultados_debug', [])
    return render(request, 'debug_resultados.html', {
        'resultados': resultados
    })

# Tela de configuração
@token_required
def configuracao_view(request):
    token = request.session['token']
    headers = {
        'Authorization': f"Bearer {token}",
        'Content-Type': 'application/json'
    }

    def post_api(endpoint):
        url = f"{config('API_BASE_URL')}/cisspoder-service/{endpoint}"
        try:
            resp = requests.post(url, json={"page": 1}, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("data", [])
        except Exception:
            logger.exception(f"❌ Erro ao buscar {endpoint}")
        return []

    empresas = post_api('cadastro_empresa')
    centros = post_api('cadastro_centroresultados')
    contas = post_api('cadastro_contabil')
    configuracoes = post_api('centroresultado_config')

    meses = [
        ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'),
        ('4', 'Abril'), ('5', 'Maio'), ('6', 'Junho'),
        ('7', 'Julho'), ('8', 'Agosto'), ('9', 'Setembro'),
        ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
    ]

    return render(request, 'configuracao.html', {
        'empresas': empresas,
        'centros': centros,
        'contas': contas,
        'configuracoes': configuracoes,
        'meses': meses
    })

# Salvar configuração
@token_required
def salvar_configuracao(request):
    if request.method == 'POST':
        headers = {
            'Authorization': f"Bearer {request.session['token']}",
            'Content-Type': 'application/json'
        }

        # Verifica se é uma ação de exclusão
        acao = request.POST.get("acao", "I")  # I = INSERT/UPDATE, D = DELETE
        
        if acao == "D":
            # Exclusão
            dados = {
                "IN_IDEEMPPREVISAO": int(request.POST["empresa"]),
                "IN_IDCTACONTABIL": int(request.POST["conta"]),
                "IN_TIPOPREVISAO": "V",  # Valor padrão para exclusão
                "IN_VALORPREVISAO": 0.0,  # Valor padrão para exclusão
                "IN_IDCENTRORESULTADO": int(request.POST["centro"]),
                "IN_MESPREVISAO": int(request.POST["mes"]) if request.POST.get("mes") else None,
                "IN_ACAO": "D"  # Indica ação de DELETE
            }

            logger.info("🗑️ Dados para exclusão:")
            logger.info(f"   - Empresa: {request.POST['empresa']}")
            logger.info(f"   - Centro: {request.POST['centro']}")
            logger.info(f"   - Conta: {request.POST['conta']}")
            logger.info(f"   - Mês: {request.POST.get('mes', 'None')}")
            logger.info(f"   - Ação: {acao}")

            logger.info("🗑️ Excluindo configuração:")
            log_json_pretty(dados)

            url = f"{config('API_BASE_URL')}/cisspoder-service/set_centroresultado_config"
            response = requests.post(url, json=[dados], headers=headers)

            logger.info(f"📥 Status: {response.status_code}")
            logger.info(f"📥 Resposta: {response.text}")

            # Retorna JSON para requisições AJAX (exclusão)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': response.status_code == 200,
                    'message': 'Configuração excluída com sucesso' if response.status_code == 200 else 'Erro ao excluir'
                })
            else:
                return redirect('configuracao')
        else:
            # Inserção/Atualização (lógica original)
            dados = {
                "IN_IDEEMPPREVISAO": int(request.POST["empresa"]),
                "IN_IDCTACONTABIL": int(request.POST["conta"]),
                "IN_TIPOPREVISAO": request.POST["tipo"],
                "IN_VALORPREVISAO": float(request.POST["valor"]),
                "IN_IDCENTRORESULTADO": int(request.POST["centro"]),
                "IN_MESPREVISAO": int(request.POST["mes"]) if request.POST.get("mes") else None,
                "IN_ACAO": "I"  # Indica ação de INSERT/UPDATE
            }

            logger.info("📤 Enviando nova configuração:")
            log_json_pretty(dados)

            url = f"{config('API_BASE_URL')}/cisspoder-service/set_centroresultado_config"
            response = requests.post(url, json=[dados], headers=headers)

            logger.info(f"📥 Status: {response.status_code}")
            logger.info(f"📥 Resposta: {response.text}")

            return redirect('configuracao')

# Atualizar configuração existente (edição inline)
@token_required
def atualizar_configuracao(request):
    if request.method == 'POST':
        headers = {
            'Authorization': f"Bearer {request.session['token']}",
            'Content-Type': 'application/json'
        }

        dados = {
            "IN_IDEEMPPREVISAO": int(request.POST["empresa"]),
            "IN_IDCTACONTABIL": int(request.POST["conta"]),
            "IN_TIPOPREVISAO": request.POST["tipo"],
            "IN_VALORPREVISAO": float(request.POST["valor"]),
            "IN_IDCENTRORESULTADO": int(request.POST["centro"]),
            "IN_MESPREVISAO": int(request.POST["mes"]) if request.POST.get("mes") else None,
            "IN_ACAO": "I"  # Indica ação de INSERT/UPDATE
        }

        logger.info("📤 Atualizando configuração existente:")
        log_json_pretty(dados)

        url = f"{config('API_BASE_URL')}/cisspoder-service/set_centroresultado_config"
        response = requests.post(url, json=[dados], headers=headers)

        logger.info(f"📥 Status: {response.status_code}")
        logger.info(f"📥 Resposta: {response.text}")

        return JsonResponse({
            'success': response.status_code == 200,
            'message': 'Configuração atualizada com sucesso' if response.status_code == 200 else 'Erro ao atualizar'
        })

    return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)

# Logout
def logout_view(request):
    request.session.flush()
    return redirect('login')
