from django.urls import path
from . import views
#from .views import painel_debug_view
from .views import debug_resultados_view


urlpatterns = [
    path('', views.login_view, name='login'),
    path('painel/', views.painel_view, name='painel'),
    path('configuracao/', views.configuracao_view, name='configuracao'),
    path('salvar_config/', views.salvar_configuracao, name='salvar_configuracao'),
    path('atualizar_config/', views.atualizar_configuracao, name='atualizar_configuracao'),
    path('configurar_conexao/', views.configurar_conexao, name='configurar_conexao'),
    path('testar_conexao/', views.testar_conexao, name='testar_conexao'),
    path('logout/', views.logout_view, name='logout'),
    #path('painel_debug/', painel_debug_view, name='painel_debug'),
    path('debug_resultados/', views.debug_resultados_view, name='debug_resultados'),
    path('configuracao_usuarios/', views.configuracao_usuarios_view, name='configuracao_usuarios'),
    path('gerenciar_usuarios_admin/', views.gerenciar_usuarios_admin, name='gerenciar_usuarios_admin'),
    path('gerenciar_usuarios_config/', views.gerenciar_usuarios_config, name='gerenciar_usuarios_config'),
    path('gerenciar_usuarios_centros/', views.gerenciar_usuarios_centros, name='gerenciar_usuarios_centros'),
    path('exportar_excel/', views.exportar_excel_view, name='exportar_excel'),
    path('buscar_configuracoes_ajax/', views.buscar_configuracoes_ajax, name='buscar_configuracoes_ajax'),

]
