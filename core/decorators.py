from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse


def token_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def aprovador_required(view_func):
    """Permite acesso apenas a usuários listados em usuarios_aprovador_liberacao.
    Para views AJAX (POST com X-Requested-With), retorna 403 JSON; para views
    normais (GET de tela), redireciona pro painel.
    """
    from . import views  # late import para evitar circular

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('login')
        username = request.session.get('username', '')
        if not views.usuario_pode_aprovar_liberacao(username):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Acesso negado'}, status=403)
            return redirect('painel')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
