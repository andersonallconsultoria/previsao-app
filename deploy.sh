#!/bin/bash

# Script de Deploy para AWS EC2
# Autor: Sistema de Previsão
# Data: $(date)

echo "🚀 Iniciando deploy da aplicação..."

# 1. Parar containers existentes
echo "📦 Parando containers existentes..."
docker-compose -f docker-compose.prod.yml down

# 2. Remover imagens antigas
echo "🧹 Removendo imagens antigas..."
docker system prune -f

# 3. Construir nova imagem
echo "🔨 Construindo nova imagem Docker..."
docker-compose -f docker-compose.prod.yml build --no-cache

# 4. Subir containers
echo "⬆️ Subindo containers..."
docker-compose -f docker-compose.prod.yml up -d

# 5. Verificar status
echo "✅ Verificando status dos containers..."
docker-compose -f docker-compose.prod.yml ps

# 6. Verificar logs
echo "📋 Últimos logs da aplicação:"
docker-compose -f docker-compose.prod.yml logs --tail=20

echo "🎉 Deploy concluído com sucesso!"
echo "🌐 Aplicação disponível em: http://localhost:8000" 