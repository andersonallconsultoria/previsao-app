# 🚀 Guia de Deploy para AWS - Preservando Configurações de Usuários

Este guia detalha o processo completo para atualizar a aplicação no servidor AWS EC2, **garantindo que o arquivo `usuarios_config.json` seja preservado**.

---

## ⚠️ **IMPORTANTE: Preservar Configurações de Usuários**

O arquivo `usuarios_config.json` contém as configurações de acesso dos usuários. Este arquivo **deve ser preservado** durante o deploy para não perder as configurações já feitas.

---

## 📋 **PASSO A PASSO COMPLETO**

### **PASSO 1: Preparar e Enviar Código para o Git (No seu PC)**

```powershell
# Navegar até a pasta do projeto
cd "D:\Projetos Python GIT\previsao_app"

# Verificar status
git status

# Adicionar todas as alterações
git add .

# Fazer commit
git commit -m "Atualização: [descreva as alterações feitas]"

# Enviar para o GitHub
git push origin main
```

**⏱️ Aguarde 2-5 minutos** para o GitHub Actions construir a nova imagem Docker.

---

### **PASSO 2: Conectar ao Servidor AWS EC2**

```powershell
# No PowerShell do seu PC
ssh -i "caminho/para/sua-chave.pem" ubuntu@SEU_IP_EC2
```

**Exemplo:**
```powershell
ssh -i "C:\Users\SeuUsuario\Downloads\minha-chave.pem" ubuntu@18.117.242.206
```

---

### **PASSO 3: Fazer Backup do Arquivo usuarios_config.json**

**⚠️ CRÍTICO: Execute este passo ANTES de qualquer atualização!**

O arquivo `usuarios_config.json` está **dentro do container Docker**, não no servidor. Precisamos copiá-lo do container para o servidor antes de fazer o backup.

```bash
# Navegar até a pasta da aplicação
cd ~/previsao-app

# Verificar se os containers estão rodando
docker-compose ps

# Identificar o nome do container (geralmente é 'previsao-app-web-1')
CONTAINER_NAME=$(docker-compose ps -q web)
# Ou use diretamente: CONTAINER_NAME="previsao-app-web-1"

# Verificar se o arquivo existe dentro do container
docker exec $CONTAINER_NAME ls -la /app/usuarios_config.json

# Se o arquivo existir, copiar do container para o servidor
docker cp $CONTAINER_NAME:/app/usuarios_config.json ~/previsao-app/usuarios_config.json

# Verificar se foi copiado
ls -la usuarios_config.json

# Fazer backup do arquivo (criar uma cópia com timestamp)
cp usuarios_config.json usuarios_config.json.backup.$(date +%Y%m%d_%H%M%S)

# Verificar se o backup foi criado
ls -la usuarios_config.json.backup.*

# Exibir o conteúdo do arquivo atual (para conferência)
cat usuarios_config.json
```

**📝 Anote o caminho do backup criado** (exemplo: `usuarios_config.json.backup.20250116_143022`)

**⚠️ NOTA:** Se o arquivo não existir no container, significa que ainda não foi criado (primeira execução). Neste caso, você pode pular o backup e o arquivo será criado automaticamente quando necessário.

---

### **PASSO 4: Parar os Containers Atuais**

```bash
# Parar e remover containers (mas mantém volumes e imagens)
docker-compose down
```

**Aguarde alguns segundos** até o comando terminar.

---

### **PASSO 5: Baixar a Nova Imagem do Docker Hub**

```bash
# Baixar a versão mais recente da imagem
docker-compose pull
```

**⏱️ Tempo estimado:** 1-3 minutos

Você verá mensagens como:
```
[+] Pulling 13/13
✔ web 12 layers [⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿] 0B/0B Pulled 13.5s
```

---

### **PASSO 6: Iniciar os Containers com a Nova Imagem**

```bash
# Iniciar containers em background
docker-compose up -d
```

**Aguarde 10-30 segundos** para os containers iniciarem completamente.

---

### **PASSO 7: Verificar se os Containers Estão Rodando**

```bash
# Verificar status dos containers
docker-compose ps
```

Você deve ver algo como:
```
NAME                    IMAGE                              STATUS
previsao-app-web-1      andersonall/previsao-app:latest    Up X seconds (health: starting)
```

**Aguarde até que o STATUS mostre "Up" e "healthy"**.

---

### **PASSO 8: Restaurar o Arquivo usuarios_config.json**

**⚠️ CRÍTICO: Execute este passo para preservar as configurações!**

```bash
# Identificar o nome do container
docker-compose ps

# Copiar o arquivo de backup para dentro do container
# Substitua 'previsao-app-web-1' pelo nome do seu container
# Substitua 'usuarios_config.json.backup.20250116_143022' pelo nome do seu backup
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json

# Verificar se o arquivo foi copiado corretamente
docker exec previsao-app-web-1 cat /app/usuarios_config.json

# Verificar permissões do arquivo
docker exec previsao-app-web-1 ls -la /app/usuarios_config.json
```

**📝 Se você não souber o nome exato do backup, liste todos:**
```bash
ls -la usuarios_config.json.backup.*
```

---

### **PASSO 9: Executar Migrações do Django (SE NECESSÁRIO)**

```bash
# Executar migrações
docker exec previsao-app-web-1 python manage.py migrate
```

Você verá mensagens como:
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, sessions
Running migrations:
  No migrations to apply.
```

---

### **PASSO 10: Verificar os Logs**

```bash
# Ver últimas 50 linhas dos logs
docker-compose logs --tail=50
```

Ou para ver em tempo real:
```bash
docker-compose logs -f
```
(Pressione `Ctrl+C` para sair)

Procure por mensagens de erro. Se tudo estiver OK, você verá:
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:8000
[INFO] Using worker: sync
```

---

### **PASSO 11: Testar a Aplicação**

#### 11.1. No navegador
Acesse: `http://SEU_IP_EC2:8000/`

**Exemplo:** `http://18.117.242.206:8000/`

#### 11.2. Verificar Configurações de Usuários

1. **Fazer login** com um usuário admin (ex: `ANDERSON.SANTOS`)

2. **Acessar "Config. Usuários"** e verificar:
   - Se os usuários configurados ainda aparecem
   - Se as permissões estão corretas
   - Se os centros de resultado vinculados estão preservados

3. **Verificar o arquivo dentro do container:**
   ```bash
   docker exec previsao-app-web-1 cat /app/usuarios_config.json
   ```

---

## 🔧 **SOLUÇÃO ALTERNATIVA: Usar Volume Docker (Recomendado para Futuro)**

Para evitar ter que copiar o arquivo manualmente a cada deploy, você pode configurar um volume Docker.

### Editar `docker-compose.prod.yml`:

Adicione um volume para o arquivo de configuração:

```yaml
version: '3.9'

services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - DJANGO_SETTINGS_MODULE=backend.settings
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./usuarios_config.json:/app/usuarios_config.json  # Adicionar esta linha
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**⚠️ IMPORTANTE:** Se você adicionar o volume, o arquivo `usuarios_config.json` deve existir na pasta `~/previsao-app/` do servidor **antes** de iniciar os containers.

---

## 🚨 **TROUBLESHOOTING**

### ❌ Erro: "usuarios_config.json não encontrado no container"

**Solução:**
```bash
# Se o arquivo não existe no container, pode ser a primeira execução
# Neste caso, o arquivo será criado automaticamente quando necessário

# Se você tem um backup no servidor, restaurar:
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json

# Verificar se foi copiado
docker exec previsao-app-web-1 ls -la /app/usuarios_config.json

# Se não tiver backup e o arquivo não existir, ele será criado automaticamente
# na primeira vez que alguém acessar a tela de Configuração de Usuários
```

### ❌ Erro: "Permission denied" ao copiar arquivo

**Solução:**
```bash
# Verificar permissões do arquivo de backup
chmod 644 usuarios_config.json.backup.*

# Tentar copiar novamente
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json
```

### ❌ Arquivo foi sobrescrito e perdeu as configurações

**Solução:**
```bash
# Restaurar do backup
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json

# Reiniciar o container para aplicar
docker-compose restart
```

---

## 📝 **CHECKLIST FINAL**

Antes de considerar o deploy concluído:

- [ ] Código commitado e enviado para o GitHub
- [ ] GitHub Actions concluído com sucesso (verde)
- [ ] Backup do `usuarios_config.json` criado
- [ ] Containers parados (`docker-compose down`)
- [ ] Nova imagem baixada (`docker-compose pull`)
- [ ] Containers iniciados (`docker-compose up -d`)
- [ ] Arquivo `usuarios_config.json` restaurado no container
- [ ] Migrações executadas (`python manage.py migrate`)
- [ ] Containers rodando e saudáveis (`docker-compose ps`)
- [ ] Aplicação acessível no navegador
- [ ] Configurações de usuários preservadas e funcionando

---

## 🎯 **RESUMO RÁPIDO (Comandos Essenciais)**

```bash
# 1. No seu PC (Windows)
cd "D:\Projetos Python GIT\previsao_app"
git add .
git commit -m "Atualização: [descrição]"
git push origin main

# 2. Aguardar GitHub Actions (2-5 minutos)

# 3. No servidor AWS (via SSH)
cd ~/previsao-app

# 3.1. BACKUP CRÍTICO (copiar do container primeiro)
CONTAINER_NAME=$(docker-compose ps -q web)
docker cp $CONTAINER_NAME:/app/usuarios_config.json ~/previsao-app/usuarios_config.json
cp usuarios_config.json usuarios_config.json.backup.$(date +%Y%m%d_%H%M%S)

# 3.2. Deploy
docker-compose down
docker-compose pull
docker-compose up -d

# 3.3. RESTAURAR CONFIGURAÇÕES
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json

# 3.4. Migrações e verificação
docker exec previsao-app-web-1 python manage.py migrate
docker-compose logs --tail=50
```

---

## 📞 **SUPORTE**

Se encontrar algum problema:

1. Verifique os logs: `docker-compose logs web`
2. Verifique o status: `docker-compose ps`
3. Verifique o arquivo: `docker exec previsao-app-web-1 cat /app/usuarios_config.json`
4. Restaure do backup se necessário

---

**Última atualização:** 2025-01-16
**Versão do guia:** 3.0 (com preservação de configurações)

