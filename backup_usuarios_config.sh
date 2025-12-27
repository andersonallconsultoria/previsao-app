#!/bin/bash

# Script para fazer backup e restaurar usuarios_config.json
# Uso: ./backup_usuarios_config.sh [backup|restore|list]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="usuarios_config.json"
BACKUP_DIR="$SCRIPT_DIR"
CONTAINER_NAME="previsao-app-web-1"

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function backup() {
    echo -e "${YELLOW}📦 Fazendo backup do arquivo usuarios_config.json...${NC}"
    
    # Verificar se o arquivo existe no container
    if docker exec $CONTAINER_NAME test -f /app/$CONFIG_FILE; then
        # Criar backup com timestamp
        BACKUP_FILE="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        
        # Copiar do container para o servidor
        docker cp ${CONTAINER_NAME}:/app/$CONFIG_FILE $BACKUP_DIR/$BACKUP_FILE
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Backup criado com sucesso: $BACKUP_FILE${NC}"
            echo -e "${GREEN}📁 Localização: $BACKUP_DIR/$BACKUP_FILE${NC}"
            
            # Exibir conteúdo do backup
            echo -e "\n${YELLOW}📄 Conteúdo do backup:${NC}"
            cat $BACKUP_DIR/$BACKUP_FILE
            echo ""
        else
            echo -e "${RED}❌ Erro ao criar backup${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Arquivo $CONFIG_FILE não encontrado no container${NC}"
        exit 1
    fi
}

function restore() {
    echo -e "${YELLOW}🔄 Restaurando arquivo usuarios_config.json...${NC}"
    
    # Listar backups disponíveis
    BACKUPS=$(ls -t $BACKUP_DIR/${CONFIG_FILE}.backup.* 2>/dev/null)
    
    if [ -z "$BACKUPS" ]; then
        echo -e "${RED}❌ Nenhum backup encontrado${NC}"
        exit 1
    fi
    
    # Pegar o backup mais recente
    LATEST_BACKUP=$(echo "$BACKUPS" | head -n 1)
    
    echo -e "${YELLOW}📦 Backup mais recente: $(basename $LATEST_BACKUP)${NC}"
    echo -e "${YELLOW}⚠️  Deseja restaurar este backup? (s/n)${NC}"
    read -r response
    
    if [[ "$response" =~ ^([sS][iI][mM]|[sS])$ ]]; then
        # Copiar backup para o container
        docker cp $LATEST_BACKUP ${CONTAINER_NAME}:/app/$CONFIG_FILE
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Arquivo restaurado com sucesso${NC}"
            
            # Verificar se foi copiado corretamente
            echo -e "\n${YELLOW}📄 Conteúdo no container:${NC}"
            docker exec $CONTAINER_NAME cat /app/$CONFIG_FILE
            echo ""
            
            # Reiniciar container para aplicar mudanças
            echo -e "${YELLOW}🔄 Reiniciando container...${NC}"
            docker-compose restart
        else
            echo -e "${RED}❌ Erro ao restaurar arquivo${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}Operação cancelada${NC}"
    fi
}

function list_backups() {
    echo -e "${YELLOW}📋 Listando backups disponíveis:${NC}"
    
    BACKUPS=$(ls -t $BACKUP_DIR/${CONFIG_FILE}.backup.* 2>/dev/null)
    
    if [ -z "$BACKUPS" ]; then
        echo -e "${RED}❌ Nenhum backup encontrado${NC}"
    else
        echo ""
        for backup in $BACKUPS; do
            SIZE=$(du -h "$backup" | cut -f1)
            DATE=$(stat -c %y "$backup" | cut -d' ' -f1,2 | cut -d'.' -f1)
            echo -e "${GREEN}📦 $(basename $backup)${NC}"
            echo -e "   Tamanho: $SIZE"
            echo -e "   Data: $DATE"
            echo ""
        done
    fi
}

function check_container() {
    if ! docker ps | grep -q $CONTAINER_NAME; then
        echo -e "${RED}❌ Container $CONTAINER_NAME não está rodando${NC}"
        echo -e "${YELLOW}💡 Execute: docker-compose up -d${NC}"
        exit 1
    fi
}

# Verificar se o container está rodando
check_container

# Processar comando
case "$1" in
    backup)
        backup
        ;;
    restore)
        restore
        ;;
    list)
        list_backups
        ;;
    *)
        echo "Uso: $0 {backup|restore|list}"
        echo ""
        echo "Comandos:"
        echo "  backup  - Fazer backup do usuarios_config.json do container"
        echo "  restore - Restaurar o backup mais recente para o container"
        echo "  list    - Listar todos os backups disponíveis"
        exit 1
        ;;
esac

