# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Visão Geral

Aplicação Django 5.2 (Python 3.11) chamada **Sistema de Previsão**. É um frontend web que **não usa o banco SQLite local de forma significativa** — em vez disso, autentica via OAuth2 e consome uma API externa (`cisspoder-auth` / `API_BASE_URL`). A configuração de runtime (credenciais, URL base, client_id, client_secret) vive no arquivo `.env`, **lido dinamicamente em tempo de execução** (não apenas no boot do Django) — ver `get_dynamic_config()` em [core/views.py](core/views.py).

## Comandos

Desenvolvimento local (PowerShell, Windows):

```powershell
# Ambiente virtual existente em .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Docker (desenvolvimento):
```powershell
docker-compose up --build
```

Docker (produção, com Gunicorn — timeout 300s, 3 workers):
```bash
docker-compose -f docker-compose.prod.yml up -d --build
# ou usar ./deploy.sh no Linux/EC2
```

Testes (placeholder — `core/tests.py` está vazio):
```powershell
python manage.py test
python manage.py test core.tests.NomeDoTeste  # teste único
```

Estáticos (necessário antes do deploy):
```powershell
python manage.py collectstatic --noinput
```

## Arquitetura

- **`backend/`** — projeto Django (settings, urls, wsgi/asgi). `backend.settings` carrega tudo via `python-decouple` lendo `.env`. `LOG_LEVEL` configurável; logger `django` fica em WARNING para reduzir ruído.
- **`core/`** — app principal e única.
  - [core/urls.py](core/urls.py) lista todas as rotas (login, painel, configuração, gerenciamento de usuários, exportação Excel, debug).
  - [core/views.py](core/views.py) (~2400 linhas) concentra **toda** a lógica: autenticação OAuth2, chamadas à API externa, agregação de resultados, geração de Excel com `openpyxl` (cores e totalizadores), endpoints AJAX. **Não há models ORM** — `core/models.py` está vazio.
  - [core/decorators.py](core/decorators.py): `@token_required` checa `request.session['token']` e redireciona ao login.
  - `core/templates/` — templates Jinja/Django (login, painel, configuracao, configuracao_usuarios, debug_resultados).
  - `core/templatetags/custom_filters.py` — filtros de template customizados.
- **`usuarios_config.json`** — controle de acesso fora do banco. Define três grupos:
  - `usuarios_admin` — acesso total
  - `usuarios_config` — pode editar configurações
  - `usuarios_centros` — mapa `usuario -> lista de IDs de centros` permitidos
  As views em `gerenciar_usuarios_*` leem/escrevem este JSON diretamente.
- **`.env`** — fonte da verdade para `API_BASE_URL`, `CLIENT_ID`, `CLIENT_SECRET`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `LOG_LEVEL`. **As views editam este arquivo em runtime** via `configurar_conexao` / `salvar_configuracao` / `atualizar_configuracao` — alterações são detectadas por mtime e invalidam `_config_cache` em [core/views.py](core/views.py).

## Pontos de Atenção

- **Sem ORM significativo**: não criar models nem migrations a menos que explicitamente pedido. Dados vêm da API externa; estado de configuração vive em `.env` e `usuarios_config.json`.
- **Cache dinâmico de config**: ao alterar leitura de variáveis, usar `get_dynamic_config(key)` em vez de `decouple.config(...)` direto, para respeitar a invalidação por mtime do `.env`.
- **Sessão guarda o token OAuth2** (`request.session['token']`); proteger novas views com `@token_required`.
- **Excel export**: o endpoint `exportar_excel/` em [core/views.py](core/views.py) usa `openpyxl` com estilos (cores, totalizadores, nome do centro) — preservar formatação ao modificar.
- **Produção** roda atrás de Gunicorn (`Dockerfile.prod`); `STATIC_ROOT = BASE_DIR / 'staticfiles'` exige `collectstatic` antes de subir.
- **Timezone**: `America/Sao_Paulo`, `LANGUAGE_CODE = 'pt-br'`.

## Deploy

Documentação detalhada em `DEPLOY.md`, `DEPLOY_PASSO_A_PASSO.md`, `GUIA_DEPLOY_AWS_PRESERVAR_CONFIG.md` e `GUIA_DEPLOY_ATUALIZACAO.md`. O fluxo em AWS preserva `.env` e `usuarios_config.json` entre deploys — ver `backup_usuarios_config.sh`.
