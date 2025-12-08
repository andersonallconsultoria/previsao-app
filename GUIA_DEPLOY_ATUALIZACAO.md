# 📋 Guia Completo de Deploy - Atualização para AWS EC2

Este guia detalha o processo completo para atualizar a aplicação no servidor AWS EC2 após fazer alterações no código.

---

## 🔄 **PASSO 1: Preparar e Enviar Código para o Git**

### 1.1. No seu computador local (Windows)

Abra o PowerShell ou Terminal e navegue até a pasta do projeto:

```powershell
cd "D:\Projetos Python GIT\previsao_app"
```

### 1.2. Verificar o status do Git

```powershell
git status
```

Isso mostrará todos os arquivos modificados/criados.

### 1.3. Adicionar todas as alterações

```powershell
git add .
```

### 1.4. Fazer commit das alterações

```powershell
git commit -m "Implementação de controle de acesso por usuários - Configuração de Usuários"
```

### 1.5. Enviar para o GitHub

```powershell
git push origin main
```

**Aguarde alguns segundos** para o push ser concluído.

---

## 🚀 **PASSO 2: Verificar GitHub Actions (Build Automático)**

### 2.1. Acessar o GitHub

1. Abra seu navegador e acesse: `https://github.com/SEU_USUARIO/SEU_REPOSITORIO`
2. Clique na aba **"Actions"** (no topo do repositório)

### 2.2. Verificar o workflow

- Você verá um workflow rodando (ou já concluído) com o nome do seu commit
- Aguarde até que o status fique **verde** (✓) com a mensagem "Build and push Docker image"
- Isso significa que a nova imagem Docker foi construída e enviada para o Docker Hub

**⏱️ Tempo estimado:** 2-5 minutos

---

## 🖥️ **PASSO 3: Conectar ao Servidor AWS EC2**

### 3.1. Conectar via SSH

No PowerShell ou Terminal (no seu computador local):

```powershell
ssh -i "caminho/para/sua-chave.pem" ubuntu@SEU_IP_EC2
```

**Exemplo:**
```powershell
ssh -i "C:\Users\SeuUsuario\Downloads\minha-chave.pem" ubuntu@18.117.242.206
```

**Nota:** Substitua `SEU_IP_EC2` pelo IP público da sua instância EC2.

---

## 📂 **PASSO 4: Navegar até a Pasta da Aplicação**

Após conectar ao servidor, execute:

```bash
cd ~/previsao-app
```

Verifique se está na pasta correta:

```bash
pwd
```

Deve mostrar: `/home/ubuntu/previsao-app`

---

## 🔄 **PASSO 5: Parar os Containers Atuais**

```bash
docker-compose down
```

Isso irá parar e remover os containers atuais (mas **não** remove as imagens nem os volumes).

**Aguarde alguns segundos** até o comando terminar.

---

## 📥 **PASSO 6: Baixar a Nova Imagem do Docker Hub**

```bash
docker-compose pull
```

Este comando baixa a versão mais recente da imagem do Docker Hub.

**⏱️ Tempo estimado:** 1-3 minutos (dependendo do tamanho da imagem)

Você verá mensagens como:
```
[+] Pulling 13/13
✔ web 12 layers [⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿] 0B/0B Pulled 13.5s
```

---

## 🚀 **PASSO 7: Iniciar os Containers com a Nova Imagem**

```bash
docker-compose up -d
```

O parâmetro `-d` faz com que os containers rodem em background (detached mode).

**Aguarde alguns segundos** para os containers iniciarem.

---

## ✅ **PASSO 8: Verificar se os Containers Estão Rodando**

```bash
docker-compose ps
```

Você deve ver algo como:

```
NAME                    IMAGE                              STATUS
previsao-app-web-1      andersonall/previsao-app:latest    Up X seconds (health: starting)
```

**Aguarde até que o STATUS mostre "Up" e "healthy"** (pode levar 10-30 segundos).

---

## 🗄️ **PASSO 9: Executar Migrações do Django (SE NECESSÁRIO)**

**⚠️ IMPORTANTE:** Execute este passo **sempre** após atualizar a aplicação, especialmente se houver mudanças no banco de dados.

### 9.1. Identificar o nome do container

```bash
docker-compose ps
```

Anote o nome do container (geralmente é `previsao-app-web-1` ou similar).

### 9.2. Executar as migrações

```bash
docker exec previsao-app-web-1 python manage.py migrate
```

**Nota:** Se o nome do container for diferente, substitua `previsao-app-web-1` pelo nome correto.

Você verá mensagens como:
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, sessions
Running migrations:
  Applying sessions.0001_initial... OK
```

---

## 📊 **PASSO 10: Verificar os Logs (Opcional, mas Recomendado)**

Para verificar se a aplicação está rodando sem erros:

```bash
docker-compose logs --tail=50
```

Ou para ver os logs em tempo real:

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

## 🧪 **PASSO 11: Testar a Aplicação**

### 11.1. No navegador

Acesse: `http://SEU_IP_EC2:8000/`

**Exemplo:** `http://18.117.242.206:8000/`

### 11.2. Testar as funcionalidades

1. **Login:**
   - Faça login com suas credenciais
   - Verifique se o username está sendo armazenado corretamente

2. **Painel:**
   - Verifique se o botão "Config. Usuários" aparece (se você for admin)
   - Verifique se o botão "Configuração" aparece apenas se você tiver permissão

3. **Configuração de Usuários:**
   - Acesse "Config. Usuários" (se for admin)
   - Teste adicionar um usuário em cada seção
   - Teste remover um usuário
   - Verifique se o arquivo `usuarios_config.json` está sendo criado

4. **Controle de Acesso:**
   - Faça logout
   - Faça login com um usuário que **não** está na lista de configuração
   - Verifique se o botão "Configuração" **não** aparece
   - Verifique se o botão "Config. Usuários" **não** aparece

---

## 🔧 **TROUBLESHOOTING (Solução de Problemas)**

### ❌ Erro: "no such table: django_session"

**Solução:**
```bash
docker exec previsao-app-web-1 python manage.py migrate
```

### ❌ Erro: "Invalid HTTP_HOST header"

**Solução:**
1. Edite o arquivo `.env`:
   ```bash
   nano ~/previsao-app/.env
   ```
2. Adicione o IP público no `ALLOWED_HOSTS`:
   ```
   ALLOWED_HOSTS=127.0.0.1,localhost,SEU_IP_PUBLICO
   ```
3. Reinicie os containers:
   ```bash
   docker-compose restart
   ```

### ❌ Container não inicia ou fica "unhealthy"

**Solução:**
1. Verifique os logs:
   ```bash
   docker-compose logs web
   ```
2. Verifique se a porta 8000 está livre:
   ```bash
   sudo netstat -tlnp | grep 8000
   ```
3. Se necessário, recrie os containers:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### ❌ Arquivo `usuarios_config.json` não está sendo criado

**Solução:**
1. Verifique as permissões da pasta:
   ```bash
   ls -la ~/previsao-app/
   ```
2. O arquivo será criado automaticamente na primeira execução. Se não aparecer, verifique os logs:
   ```bash
   docker-compose logs web | grep usuarios
   ```

---

## 📝 **CHECKLIST FINAL**

Antes de considerar o deploy concluído, verifique:

- [ ] Código commitado e enviado para o GitHub
- [ ] GitHub Actions concluído com sucesso (verde)
- [ ] Nova imagem baixada no servidor (`docker-compose pull`)
- [ ] Containers rodando (`docker-compose ps` mostra "Up" e "healthy")
- [ ] Migrações executadas (`python manage.py migrate`)
- [ ] Aplicação acessível no navegador
- [ ] Login funcionando
- [ ] Botões aparecem/desaparecem conforme permissões
- [ ] Configuração de usuários funcionando
- [ ] Arquivo `usuarios_config.json` sendo criado/atualizado

---

## 🎯 **RESUMO RÁPIDO (Comandos Essenciais)**

```bash
# 1. No seu PC (Windows)
cd "D:\Projetos Python GIT\previsao_app"
git add .
git commit -m "Implementação de controle de acesso por usuários"
git push origin main

# 2. Aguardar GitHub Actions (2-5 minutos)

# 3. No servidor AWS (via SSH)
cd ~/previsao-app
docker-compose down
docker-compose pull
docker-compose up -d
docker exec previsao-app-web-1 python manage.py migrate
docker-compose logs --tail=50
```

---

## 📞 **SUPORTE**

Se encontrar algum problema não listado aqui, verifique:
1. Os logs do container: `docker-compose logs web`
2. O status dos containers: `docker-compose ps`
3. As permissões dos arquivos: `ls -la ~/previsao-app/`

---

**Última atualização:** 2025-01-XX
**Versão do guia:** 2.0
