# 🚀 Guia Passo a Passo - Atualizar e Deploy no AWS

## 📋 Visão Geral do Processo

1. ✅ **Local**: Commit e push das alterações para GitHub
2. ⏳ **GitHub Actions**: Build automático da imagem Docker e push para Docker Hub
3. 🖥️ **AWS EC2**: Pull da nova imagem e reiniciar containers

---

## 📝 PASSO 1: Preparar e Enviar Alterações (Local)

### 1.1 Verificar alterações
```bash
# Ver o que foi alterado
git status

# Ver as diferenças
git diff
```

### 1.2 Adicionar arquivos alterados
```bash
# Adicionar todos os arquivos modificados
git add .

# OU adicionar arquivos específicos
git add core/views.py
```

### 1.3 Fazer commit
```bash
# Commit com mensagem descritiva
git commit -m "feat: adicionar limit:1000 na busca de contas contábeis"
```

### 1.4 Enviar para GitHub
```bash
# Push para o repositório
git push origin main
```

**✅ Após o push, o GitHub Actions iniciará automaticamente o build da imagem Docker!**

---

## ⏳ PASSO 2: Aguardar Build no GitHub Actions

### 2.1 Verificar o progresso do build

1. Acesse seu repositório no GitHub
2. Clique na aba **"Actions"**
3. Verifique o workflow em execução
4. Aguarde até ver: **✅ Build completed successfully**

**⏱️ Tempo estimado: 5-10 minutos**

### 2.2 Verificar se a imagem foi enviada para Docker Hub

1. Acesse [Docker Hub](https://hub.docker.com/)
2. Entre na sua conta
3. Verifique se a imagem `andersonall/previsao-app:latest` foi atualizada
4. Confirme a data/hora da última atualização

**✅ Quando a imagem aparecer atualizada no Docker Hub, pode prosseguir!**

---

## 🖥️ PASSO 3: Conectar ao Servidor AWS EC2

### 3.1 Conectar via SSH

**Windows (PowerShell ou CMD):**
```bash
ssh -i "caminho/para/sua-chave.pem" ubuntu@SEU-IP-EC2
```

**Exemplo:**
```bash
ssh -i "C:\Users\SeuUsuario\Downloads\minha-chave.pem" ubuntu@18.117.242.206
```

**Linux/Mac:**
```bash
ssh -i ~/sua-chave.pem ubuntu@SEU-IP-EC2
```

### 3.2 Verificar conexão
```bash
# Deve aparecer algo como:
# ubuntu@ip-172-31-XX-XX:~$
```

---

## 📦 PASSO 4: Atualizar Aplicação no Servidor AWS

### 4.1 Navegar para o diretório da aplicação
```bash
cd ~/previsao-app
```

**OU se estiver em outro diretório:**
```bash
# Encontrar o diretório
find ~ -name "docker-compose.yml" -type f 2>/dev/null

# Depois navegar até ele
cd /caminho/encontrado
```

### 4.2 Verificar containers em execução
```bash
# Ver status atual
docker-compose ps

# Deve mostrar algo como:
# NAME                    IMAGE                          STATUS
# previsao-app-web-1      andersonall/previsao-app:latest Up X minutes
```

### 4.3 Parar containers (sem perder dados)
```bash
# Parar containers graciosamente
docker-compose down

# OU se usar docker-compose.prod.yml:
docker-compose -f docker-compose.prod.yml down
```

### 4.4 Atualizar imagem Docker do Docker Hub
```bash
# Fazer pull da nova imagem
docker-compose pull

# OU se usar docker-compose.prod.yml:
docker-compose -f docker-compose.prod.yml pull
```

**⏱️ Isso pode levar alguns minutos dependendo do tamanho da imagem**

### 4.5 Verificar se a imagem foi atualizada
```bash
# Ver imagens locais
docker images | grep previsao-app

# Verificar a data/hora da imagem
docker images andersonall/previsao-app:latest
```

### 4.6 Reiniciar containers com a nova imagem
```bash
# Subir containers com a nova imagem
docker-compose up -d

# OU se usar docker-compose.prod.yml:
docker-compose -f docker-compose.prod.yml up -d
```

### 4.7 Verificar se está rodando corretamente
```bash
# Ver status dos containers
docker-compose ps

# Deve mostrar STATUS: Up X seconds (healthy)
```

### 4.8 Verificar logs (opcional, mas recomendado)
```bash
# Ver logs em tempo real
docker-compose logs -f

# OU ver apenas os últimos logs
docker-compose logs --tail=50

# Para sair dos logs, pressione: Ctrl + C
```

---

## ✅ PASSO 5: Verificar se Está Funcionando

### 5.1 Testar aplicação localmente no servidor
```bash
# Testar se responde
curl http://localhost:8000/

# Deve retornar HTML da página de login
```

### 5.2 Verificar health check
```bash
# Ver status detalhado
docker-compose ps

# Verificar se está "healthy"
docker inspect previsao-app-web-1 | grep -A 5 Health
```

### 5.3 Testar no navegador
1. Abra seu navegador
2. Acesse: `http://SEU-IP-EC2:8000`
3. Verifique se a aplicação carrega normalmente
4. Teste fazer login e acessar a tela de Configuração
5. Teste a busca de contas contábeis para verificar se o `limit:1000` está funcionando

---

## 🔍 PASSO 6: Verificar se a Atualização Funcionou

### 6.1 Verificar logs da aplicação
```bash
# Ver logs recentes procurando por "cadastro_contabil"
docker-compose logs | grep cadastro_contabil

# Deve mostrar algo como:
# [INFO] Endpoint 'cadastro_contabil' - Página 1: X registros
```

### 6.2 Verificar se o limit está sendo enviado
```bash
# Ver logs detalhados
docker-compose logs web | grep -i "limit\|page"

# OU ver todos os logs
docker-compose logs web
```

### 6.3 Testar funcionalidade
1. Acesse a tela de **Configuração**
2. Clique no campo **"Conta Contábil"**
3. Digite para buscar
4. Verifique se está funcionando corretamente

---

## 🚨 Troubleshooting (Solução de Problemas)

### Problema: "Error response from daemon: pull access denied"
```bash
# Fazer login no Docker Hub
docker login

# Digite seu username e password do Docker Hub
```

### Problema: Container não inicia
```bash
# Ver logs detalhados
docker-compose logs

# Verificar se há erros
docker-compose logs | grep -i error
```

### Problema: Imagem não atualizou
```bash
# Forçar pull sem cache
docker-compose pull --no-cache

# Remover imagem antiga
docker rmi andersonall/previsao-app:latest

# Fazer pull novamente
docker-compose pull
```

### Problema: Porta 8000 já em uso
```bash
# Verificar o que está usando a porta
sudo netstat -tulpn | grep :8000

# Parar containers
docker-compose down

# Subir novamente
docker-compose up -d
```

### Problema: Erro "no such table: django_session"
```bash
# Executar migrações
docker exec previsao-app-web-1 python manage.py migrate

# Verificar se funcionou
docker-compose logs | grep migrate
```

---

## 📊 Comandos Úteis para Monitoramento

### Ver status dos containers
```bash
docker-compose ps
```

### Ver uso de recursos
```bash
docker stats
```

### Ver logs em tempo real
```bash
docker-compose logs -f web
```

### Reiniciar apenas um container
```bash
docker-compose restart web
```

### Ver informações da imagem
```bash
docker inspect andersonall/previsao-app:latest
```

---

## ✅ Checklist Final

Antes de considerar o deploy completo, verifique:

- [ ] ✅ Alterações commitadas e enviadas para GitHub
- [ ] ✅ GitHub Actions completou o build com sucesso
- [ ] ✅ Imagem atualizada no Docker Hub
- [ ] ✅ Conectado ao servidor AWS via SSH
- [ ] ✅ Containers parados (`docker-compose down`)
- [ ] ✅ Nova imagem baixada (`docker-compose pull`)
- [ ] ✅ Containers reiniciados (`docker-compose up -d`)
- [ ] ✅ Containers estão "Up" e "healthy"
- [ ] ✅ Aplicação acessível no navegador
- [ ] ✅ Funcionalidade testada e funcionando
- [ ] ✅ Logs não mostram erros críticos

---

## 🎯 Resumo Rápido (Comandos Essenciais)

```bash
# 1. Local - Commit e Push
git add .
git commit -m "sua mensagem"
git push origin main

# 2. Aguardar GitHub Actions (5-10 min)

# 3. AWS EC2 - Atualizar
cd ~/previsao-app
docker-compose down
docker-compose pull
docker-compose up -d
docker-compose ps
docker-compose logs -f
```

---

**🎉 Pronto! Sua aplicação está atualizada e rodando no AWS!**


