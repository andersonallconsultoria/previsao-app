from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Retorna o valor do dicionário com base na chave fornecida"""
    return dictionary.get(str(key), {})

@register.filter
def dict_get(obj, key):
    """Permite acessar uma chave dentro de um dicionário aninhado"""
    return obj.get(key) if isinstance(obj, dict) else None

@register.filter
def zfill(value, size=2):
    """Preenche o valor com zeros à esquerda até o tamanho desejado"""
    try:
        return str(value).zfill(int(size))
    except Exception:
        return value

@register.filter
def get_totalizador(totais, chave):
    """Retorna o valor do totalizador para uma chave específica"""
    try:
        return totais.get(chave, 0)
    except Exception:
        return 0

@register.filter
def calcular_colspan(meses):
    """Calcula o colspan baseado no número de meses"""
    try:
        return len(meses) * 3 + 1
    except Exception:
        return 37  # Valor padrão para 12 meses

@register.filter
def get_valor_color(realizado, previsto):
    """Retorna a classe CSS baseada na comparação entre realizado e previsto"""
    try:
        # Garantir que os valores são numéricos
        if realizado is None or realizado == "":
            realizado_val = 0
        else:
            realizado_val = float(realizado)
            
        if previsto is None or previsto == "":
            previsto_val = 0
        else:
            previsto_val = float(previsto)
        
        # Se realizado é zero ou negativo, mantém cor padrão
        if realizado_val <= 0:
            return ""
        
        # Se realizado > previsto, vermelho claro (alerta)
        if realizado_val > previsto_val:
            return "bg-danger bg-opacity-25"
        
        # Se realizado < previsto, verde claro (positivo)
        if realizado_val < previsto_val:
            return "bg-success bg-opacity-25"
        
        # Se realizado = previsto, mantém cor padrão
        return ""
    except (ValueError, TypeError, AttributeError):
        return ""
