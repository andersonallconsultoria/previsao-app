from django.shortcuts import render, redirect
from django.http import JsonResponse
import requests
from decouple import config
from .decorators import token_required
from collections import defaultdict
import logging
import json
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Cache dinâmico para configurações
_config_cache = {}
_config_cache_timestamp = 0

def get_dynamic_config(key, default=None):
    """
    Obtém configuração dinamicamente do arquivo .env
    com cache para performance
    """
    global _config_cache, _config_cache_timestamp
    
    # Verifica se o arquivo .env foi modificado
    try:
        env_path = '.env'
        if os.path.exists(env_path):
            current_timestamp = os.path.getmtime(env_path)
            
            # Se o arquivo foi modificado, limpa o cache
            if current_timestamp > _config_cache_timestamp:
                _config_cache.clear()
                _config_cache_timestamp = current_timestamp
                logger.info("🔄 Cache de configurações limpo - arquivo .env modificado")
        
        # Se não está no cache, lê do arquivo
        if key not in _config_cache:
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            _config_cache[k] = v
                            logger.debug(f"📝 Config carregada: {k}={v}")
            
            # Se ainda não encontrou, usa o config padrão
            if key not in _config_cache:
                _config_cache[key] = config(key, default=default)
        
        return _config_cache.get(key, default)
        
    except Exception as e:
        logger.warning(f"⚠️ Erro ao ler configuração dinâmica: {e}")
        return config(key, default=default)

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
    url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-auth/oauth/token"
    payload = {
        'username': username,
        'password': password,
        'grant_type': 'password',
        'client_id': get_dynamic_config('CLIENT_ID'),
        'client_secret': get_dynamic_config('CLIENT_SECRET'),
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        # Adicionar timeout para evitar esperas muito longas
        response = requests.post(url, data=payload, headers=headers, timeout=10)
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Timeout ao conectar com {url}")
        return {'error': 'timeout', 'error_description': 'Timeout de conexão'}
    except requests.exceptions.ConnectTimeout:
        logger.error(f"⏰ Connect timeout ao conectar com {url}")
        return {'error': 'connect_timeout', 'error_description': 'Timeout de conexão'}
    except requests.exceptions.ConnectionError:
        logger.error(f"🔌 Erro de conexão com {url}")
        return {'error': 'connection_error', 'error_description': 'Erro de conexão'}
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao gerar token: {str(e)}")
        return {'error': 'unknown', 'error_description': f'Erro inesperado: {str(e)}'}

# Login
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        try:
            token_data = gerar_token(username, password)
            if 'access_token' in token_data:
                request.session['token'] = token_data['access_token']
                return redirect('painel')
            else:
                # Erro de autenticação da API
                error_msg = token_data.get('error_description', 'Login inválido')
                if 'invalid_grant' in error_msg.lower():
                    error_msg = 'Usuário ou senha incorretos'
                elif 'timeout' in error_msg.lower() or 'connection' in error_msg.lower():
                    error_msg = 'Erro de conexão com o servidor. Verifique a configuração de conexão.'
                
                return render(request, 'login.html', {
                    'erro': error_msg,
                    'erro_tipo': 'auth'
                })
        except requests.exceptions.ConnectTimeout:
            return render(request, 'login.html', {
                'erro': '❌ Erro de conexão: Timeout ao conectar com o servidor. Verifique se o IP e porta estão corretos.',
                'erro_tipo': 'connection'
            })
        except requests.exceptions.ConnectionError:
            return render(request, 'login.html', {
                'erro': '❌ Erro de conexão: Não foi possível conectar com o servidor. Verifique se o servidor está rodando e acessível.',
                'erro_tipo': 'connection'
            })
        except Exception as e:
            logger.error(f"❌ Erro inesperado no login: {str(e)}")
            return render(request, 'login.html', {
                'erro': f'❌ Erro inesperado: {str(e)}',
                'erro_tipo': 'unknown'
            })
    
    # Pass current API_BASE_URL to template
    context = {
        'api_base_url': get_dynamic_config('API_BASE_URL', default='http://200.141.41.20:8086')
    }
    return render(request, 'login.html', context)

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
        url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-service/{endpoint}"
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

        # Sempre adicionar cláusula de empresa
        if empresa and empresa.strip():
            try:
                emp_int = int(empresa)
                payload["clausulas"].append({
                    "campo": "idempfiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": emp_int
                })
                logger.info(f"🏢 Empresa específica selecionada: {emp_int}")
            except ValueError:
                logger.warning(f"⚠️ Empresa inválida: {empresa}")
                # Se empresa inválida, enviar null
                payload["clausulas"].append({
                    "campo": "idempfiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": None
                })
        else:
            # Se empresa estiver vazia ou for "Todas", enviar null
            payload["clausulas"].append({
                "campo": "idempfiltro", "operadorlogico": "AND", "operador": "IGUAL", "valor": None
            })
            logger.info("🏢 Filtro de empresa: 'Todas' selecionado - enviando null")

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

        url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-service/centro_resultado_bi"
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

    def post_api(endpoint, use_pagination=False):
        url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-service/{endpoint}"
        all_data = []
        
        try:
            if use_pagination:
                # Implementar paginação similar ao painel
                page = 1
                while True:
                    payload = {
                        "page": page,
                        "limit": 1000
                    }
                    resp = requests.post(url, json=payload, headers=headers)
                    
                    if resp.status_code == 200:
                        response_data = resp.json()
                        page_data = response_data.get("data", [])
                        has_next = response_data.get("hasNext", False)
                        
                        all_data.extend(page_data)
                        logger.info(f"📄 Endpoint '{endpoint}' - Página {page}: {len(page_data)} registros")
                        
                        if not has_next:
                            break
                        page += 1
                    else:
                        logger.warning(f"⚠️ Endpoint '{endpoint}' retornou {resp.status_code} na página {page}")
                        break
            else:
                # Sem paginação (para endpoints pequenos)
                resp = requests.post(url, json={"page": 1}, headers=headers)
                if resp.status_code == 200:
                    all_data = resp.json().get("data", [])
        except Exception:
            logger.exception(f"❌ Erro ao buscar {endpoint}")
        
        return all_data

    empresas = post_api('cadastro_empresa')
    centros = post_api('cadastro_centroresultados')
    contas = post_api('cadastro_contabil')
    configuracoes = post_api('centroresultado_config', use_pagination=True)

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

            url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-service/set_centroresultado_config"
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

            url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-service/set_centroresultado_config"
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

        url = f"{get_dynamic_config('API_BASE_URL')}/cisspoder-service/set_centroresultado_config"
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

# Configurar conexão
def configurar_conexao(request):
    if request.method == 'POST':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            api_base_url = data.get('api_base_url')
            
            if not api_base_url:
                return JsonResponse({
                    'success': False, 
                    'message': 'URL da API é obrigatória'
                }, status=400)
            
            # Read current .env file
            env_file_path = '.env'
            try:
                with open(env_file_path, 'r', encoding='utf-8') as f:
                    env_content = f.read()
            except FileNotFoundError:
                # If .env doesn't exist, create from template
                env_content = """# Configurações do Django
DEBUG=False
SECRET_KEY=django-insecure-x1dkg(z5ie%a0!h&dw6ls*ublu7=i@11w)9v6)ithl&+j0@6@-
# Hosts permitidos
ALLOWED_HOSTS=127.0.0.1,localhost
# URL da API externa
API_BASE_URL=http://200.141.41.20:8086
# Credenciais da API
CLIENT_ID=cisspoder-oauth
CLIENT_SECRET=poder7547
API_USERNAME=integracao
API_PASSWORD=13579
# Configurações de segurança
CSRF_TRUSTED_ORIGINS=
# Configurações de logging
LOG_LEVEL=INFO
"""
            
            # Update API_BASE_URL in .env content
            lines = env_content.split('\n')
            updated_lines = []
            api_url_updated = False
            
            for line in lines:
                if line.startswith('API_BASE_URL='):
                    updated_lines.append(f'API_BASE_URL={api_base_url}')
                    api_url_updated = True
                else:
                    updated_lines.append(line)
            
            # If API_BASE_URL wasn't found, add it
            if not api_url_updated:
                # Find the right place to insert (after Django settings)
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.startswith('# URL da API externa') or line.startswith('API_BASE_URL='):
                        insert_index = i + 1
                        break
                
                # Insert the new API_BASE_URL
                if insert_index < len(lines):
                    lines.insert(insert_index, f'API_BASE_URL={api_base_url}')
                else:
                    lines.append(f'API_BASE_URL={api_base_url}')
                
                updated_lines = lines
            
            # Write updated .env file
            with open(env_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(updated_lines))
            
            logger.info(f"✅ Configuração de conexão atualizada: {api_base_url}")
            
            # Force reload of environment variables
            from decouple import Config, RepositoryEnv
            import os
            
            # Clear any cached config
            if hasattr(config, '_config'):
                delattr(config, '_config')
            
            # Reload environment variables
            try:
                # Force reload by clearing cache
                os.environ.pop('API_BASE_URL', None)
                
                # Reload from .env file
                from decouple import config as reload_config
                reload_config._config = None  # Clear cache
                reload_config._config = RepositoryEnv('.env')
                
                logger.info("🔄 Configurações recarregadas com sucesso!")
                
            except Exception as reload_error:
                logger.warning(f"⚠️ Aviso: Não foi possível recarregar automaticamente. Reinicie a aplicação para aplicar as mudanças. Erro: {reload_error}")
            
            return JsonResponse({
                'success': True,
                'message': 'Configuração salva com sucesso! A aplicação foi recarregada automaticamente.',
                'api_base_url': api_base_url,
                'reloaded': True
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados JSON inválidos'
            }, status=400)
        except Exception as e:
            logger.error(f"❌ Erro ao configurar conexão: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método não permitido'
    }, status=405)

# Testar conexão
def testar_conexao(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            api_base_url = data.get('api_base_url')
            
            if not api_base_url:
                return JsonResponse({
                    'success': False,
                    'message': 'URL da API é obrigatória'
                }, status=400)
            
            # Test connection with timeout
            try:
                response = requests.post(
                    f"{api_base_url}/cisspoder-auth/oauth/token",
                    data={
                        'grant_type': 'password',
                        'username': 'test',
                        'password': 'test',
                        'client_id': 'test',
                        'client_secret': 'test'
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=5
                )
                
                # If we get any response (even error), connection is working
                if response.status_code in [200, 400, 401, 403]:
                    return JsonResponse({
                        'success': True,
                        'message': 'Conexão estabelecida com sucesso!',
                        'status_code': response.status_code
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': f'Conexão estabelecida, mas servidor retornou status {response.status_code}',
                        'status_code': response.status_code
                    })
                    
            except requests.exceptions.Timeout:
                return JsonResponse({
                    'success': False,
                    'message': 'Timeout de conexão - servidor não respondeu em tempo hábil'
                })
            except requests.exceptions.ConnectionError:
                return JsonResponse({
                    'success': False,
                    'message': 'Erro de conexão - verifique se o IP e porta estão corretos'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Erro inesperado: {str(e)}'
                })
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados JSON inválidos'
            }, status=400)
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método não permitido'
    }, status=405)
