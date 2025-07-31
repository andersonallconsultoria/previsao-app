from functools import wraps
from django.shortcuts import redirect

def token_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if 'token' not in request.session:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view
