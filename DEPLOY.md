# 🚀 Guia de Deploy - Sistema de Previsão

## 📋 Pré-requisitos

### Local (Desenvolvimento)
- Docker Desktop
- Git
- Editor de código

### AWS EC2
- Instância EC2 (Ubuntu 22.04 LTS recomendado)
- Security Group configurado
- Chave SSH

## 🐳 Passo 1: Preparação Local

### 1.1 Testar Docker Localmente
```bash
# Construir imagem
docker build -f Dockerfile.prod -t previsao-app .

# Testar localmente
docker run -p 8000:8000 --env-file .env previsao-app
```

### 1.2 Verificar arquivos necessários
- ✅ `Dockerfile.prod`
- ✅ `docker-compose.prod.yml`
- ✅ `requirements.txt` (com gunicorn)
- ✅ `.env` (com variáveis de produção)
- ✅ `deploy.sh`

## ☁️ Passo 2: Configurar AWS EC2

### 2.1 Criar Instância EC2
```bash
# Especificações recomendadas:
# - Tipo: t3.medium ou t3.large
# - SO: Ubuntu 22.04 LTS
# - Storage: 20GB gp3
# - Security Group: Porta 22 (SSH) e 80/443 (HTTP/HTTPS)
```

### 2.2 Conectar via SSH
```bash
ssh -i sua-chave.pem ubuntu@seu-ip-ec2
```

### 2.3 Atualizar sistema
```bash
sudo apt update && sudo apt upgrade -y
```

## 🛠️ Passo 3: Instalar Dependências no EC2

### 3.1 Instalar Docker
```bash
# Remover versões antigas
sudo apt remove docker docker-engine docker.io containerd runc

# Instalar dependências
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Adicionar chave GPG oficial do Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Adicionar repositório
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Adicionar usuário ao grupo docker
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Reiniciar sessão SSH
exit
# Reconectar: ssh -i sua-chave.pem ubuntu@seu-ip-ec2
```

### 3.2 Verificar instalação
```bash
docker --version
docker-compose --version
```

## 📦 Passo 4: Deploy da Aplicação

### 4.1 Clonar repositório
```bash
# No EC2
git clone https://github.com/seu-usuario/previsao_app.git
cd previsao_app
```

### 4.2 Configurar variáveis de ambiente
```bash
# Criar arquivo .env
nano .env

# Adicionar variáveis (exemplo):
API_BASE_URL=http://200.141.41.20:8086
CLIENT_ID=seu_client_id
CLIENT_SECRET=seu_client_secret
DEBUG=False
ALLOWED_HOSTS=seu-ip-ec2,seu-dominio.com
```

### 4.3 Tornar script executável
```bash
chmod +x deploy.sh
```

### 4.4 Executar deploy
```bash
./deploy.sh
```

## 🔧 Passo 5: Configurações Adicionais

### 5.1 Configurar Nginx (Opcional)
```bash
# Instalar Nginx
sudo apt install nginx

# Configurar proxy reverso
sudo nano /etc/nginx/sites-available/previsao-app

# Conteúdo:
server {
    listen 80;
    server_name seu-ip-ec2;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Ativar site
sudo ln -s /etc/nginx/sites-available/previsao-app /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 5.2 Configurar SSL (Opcional)
```bash
# Instalar Certbot
sudo apt install certbot python3-certbot-nginx

# Obter certificado
sudo certbot --nginx -d seu-dominio.com
```

## 📊 Passo 6: Monitoramento

### 6.1 Verificar logs
```bash
# Logs da aplicação
docker-compose -f docker-compose.prod.yml logs -f

# Logs de um container específico
docker-compose -f docker-compose.prod.yml logs -f web
```

### 6.2 Verificar status
```bash
# Status dos containers
docker-compose -f docker-compose.prod.yml ps

# Uso de recursos
docker stats
```

### 6.3 Health Check
```bash
# Testar aplicação
curl http://localhost:8000/
```

## 🔄 Passo 7: Atualizações

### 7.1 Deploy de atualizações
```bash
# Puxar código atualizado
git pull origin main

# Executar deploy
./deploy.sh
```

### 7.2 Rollback (se necessário)
```bash
# Voltar para versão anterior
git checkout HEAD~1
./deploy.sh
```

## 🚨 Troubleshooting

### Problema: Container não inicia
```bash
# Verificar logs
docker-compose -f docker-compose.prod.yml logs

# Verificar variáveis de ambiente
docker-compose -f docker-compose.prod.yml config
```

### Problema: Porta já em uso
```bash
# Verificar processos
sudo netstat -tulpn | grep :8000

# Parar processo
sudo kill -9 PID
```

### Problema: Erro de permissão
```bash
# Verificar permissões
ls -la

# Corrigir permissões
chmod 755 deploy.sh
```

## 📞 Suporte

Para problemas ou dúvidas:
- Verificar logs: `docker-compose -f docker-compose.prod.yml logs`
- Verificar status: `docker-compose -f docker-compose.prod.yml ps`
- Reiniciar: `docker-compose -f docker-compose.prod.yml restart`

## 🎯 Checklist Final

- [ ] Docker instalado no EC2
- [ ] Aplicação rodando em container
- [ ] Porta 8000 acessível
- [ ] Variáveis de ambiente configuradas
- [ ] Logs funcionando
- [ ] Health check passando
- [ ] Nginx configurado (opcional)
- [ ] SSL configurado (opcional)
- [ ] Monitoramento ativo

**🎉 Deploy concluído com sucesso!** 