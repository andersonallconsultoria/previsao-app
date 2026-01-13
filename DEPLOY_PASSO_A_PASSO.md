# 🚀 Deploy Passo a Passo - AWS EC2

## ⚠️ IMPORTANTE: Preservar Configurações de Usuários

O arquivo `usuarios_config.json` contém as configurações de acesso dos usuários e **deve ser preservado** durante o deploy.

---

## 📋 PASSO A PASSO COMPLETO

### **PASSO 1: Fazer Backup do usuarios_config.json (No Servidor AWS)**

Execute no servidor AWS (você já está conectado):

```bash
# 1. Verificar se o arquivo existe dentro do container
docker exec previsao-app-web-1 ls -la /app/usuarios_config.json
```

**Se o arquivo existir:**
```bash
# 2. Copiar do container para o servidor
docker cp previsao-app-web-1:/app/usuarios_config.json ~/previsao-app/usuarios_config.json

# 3. Fazer backup com timestamp
cp usuarios_config.json usuarios_config.json.backup.$(date +%Y%m%d_%H%M%S)

# 4. Verificar backup criado
ls -la usuarios_config.json.backup.*

# 5. Anotar o nome do backup (exemplo: usuarios_config.json.backup.20250116_143022)
```

**Se o arquivo NÃO existir:**
- Significa que ainda não foi criado (primeira execução)
- Você pode pular o backup e continuar
- O arquivo será criado automaticamente quando necessário

---

### **PASSO 2: No seu PC (Windows) - Preparar e Enviar Código**

Abra o PowerShell no seu PC e execute:

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

### **PASSO 3: Verificar GitHub Actions**

1. Acesse: `https://github.com/SEU_USUARIO/SEU_REPOSITORIO`
2. Clique na aba **"Actions"**
3. Aguarde até que o workflow fique **verde (✓)** com "Build and push Docker image"

---

### **PASSO 4: No Servidor AWS - Parar Containers**

```bash
# Parar e remover containers (mantém volumes e imagens)
docker-compose down
```

**Aguarde alguns segundos** até o comando terminar.

---

### **PASSO 5: Baixar Nova Imagem do Docker Hub**

```bash
# Baixar a versão mais recente
docker-compose pull
```

**⏱️ Tempo estimado:** 1-3 minutos

Você verá mensagens como:
```
[+] Pulling 13/13
✔ web 12 layers [⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿] 0B/0B Pulled 13.5s
```

---

### **PASSO 6: Iniciar Containers com Nova Imagem**

```bash
# Iniciar containers em background
docker-compose up -d
```

**Aguarde 10-30 segundos** para os containers iniciarem.

---

### **PASSO 7: Verificar Status dos Containers**

```bash
# Verificar se estão rodando
docker-compose ps
```

Aguarde até que o STATUS mostre **"Up" e "healthy"**.

---

### **PASSO 8: Restaurar usuarios_config.json (SE FEZ BACKUP)**

**⚠️ CRÍTICO: Execute este passo apenas se você fez backup no PASSO 1!**

```bash
# Substitua 'usuarios_config.json.backup.20250116_143022' pelo nome do seu backup
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json

# Verificar se foi copiado corretamente
docker exec previsao-app-web-1 cat /app/usuarios_config.json

# Verificar permissões
docker exec previsao-app-web-1 ls -la /app/usuarios_config.json
```

**Se você não fez backup** (arquivo não existia), pule este passo. O arquivo será criado automaticamente quando necessário.

---

### **PASSO 9: Executar Migrações do Django**

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

### **PASSO 10: Verificar Logs**

```bash
# Ver últimas 50 linhas dos logs
docker-compose logs --tail=50
```

Procure por erros. Se tudo estiver OK, você verá:
```
[INFO] Starting gunicorn 21.2.0
[INFO] Listening at: http://0.0.0.0:8000
[INFO] Using worker: sync
```

---

### **PASSO 11: Testar Aplicação**

1. **No navegador:** Acesse `http://SEU_IP_EC2:8000/`

2. **Fazer login** com um usuário admin

3. **Verificar Configurações de Usuários:**
   - Acessar "Config. Usuários"
   - Verificar se os usuários configurados ainda aparecem
   - Verificar se as permissões estão corretas

4. **Verificar arquivo no container:**
   ```bash
   docker exec previsao-app-web-1 cat /app/usuarios_config.json
   ```

---

## ✅ CHECKLIST FINAL

- [ ] Backup do `usuarios_config.json` criado (se existia)
- [ ] Código commitado e enviado para GitHub
- [ ] GitHub Actions concluído (verde)
- [ ] Containers parados (`docker-compose down`)
- [ ] Nova imagem baixada (`docker-compose pull`)
- [ ] Containers iniciados (`docker-compose up -d`)
- [ ] Arquivo `usuarios_config.json` restaurado (se tinha backup)
- [ ] Migrações executadas (`python manage.py migrate`)
- [ ] Containers rodando e saudáveis (`docker-compose ps`)
- [ ] Aplicação acessível no navegador
- [ ] Configurações de usuários preservadas e funcionando

---

## 🚨 TROUBLESHOOTING

### ❌ Erro ao copiar arquivo para container

```bash
# Verificar se o container está rodando
docker-compose ps

# Tentar novamente
docker cp usuarios_config.json.backup.20250116_143022 previsao-app-web-1:/app/usuarios_config.json
```

### ❌ Container não inicia

```bash
# Ver logs
docker-compose logs web

# Recriar containers
docker-compose down
docker-compose up -d
```

### ❌ Arquivo usuarios_config.json não encontrado

Se o arquivo não existir, ele será criado automaticamente na primeira vez que alguém acessar a tela de "Configuração de Usuários". Isso é normal.

---

**Pronto! Siga os passos na ordem e me avise se encontrar algum problema.**





