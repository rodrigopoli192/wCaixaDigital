@echo off
echo ===============================================
echo    Sistema de Caixa com NFS-e - Setup
echo ===============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Instale o Python 3.12+
    pause
    exit /b 1
)

echo [1/6] Criando ambiente virtual...
if not exist .venv (
    python -m venv .venv
)

echo [2/6] Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo [3/6] Instalando dependencias...
pip install --upgrade pip
pip install -r requirements\local.txt

echo [4/6] Criando diretorios necessarios...
if not exist logs mkdir logs
if not exist media mkdir media
if not exist staticfiles mkdir staticfiles

echo [5/6] Aplicando migracoes...
python manage.py migrate

echo [6/6] Coletando arquivos estaticos...
python manage.py collectstatic --noinput

echo.
echo ===============================================
echo    Setup concluido com sucesso!
echo ===============================================
echo.
echo Proximos passos:
echo   1. Criar superusuario: python manage.py createsuperuser
echo   2. Carregar dados exemplo: python manage.py loaddata fixtures\sample_data.json
echo   3. Rodar servidor: python manage.py runserver
echo.
echo Acesso:
echo   - Aplicacao: http://localhost:8000
echo   - Admin: http://localhost:8000/admin/
echo.
pause
