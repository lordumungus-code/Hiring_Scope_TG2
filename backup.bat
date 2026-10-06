@echo off
echo ========================================
echo   BACKUP DO BANCO - HIRINGSCOPE
echo ========================================
echo.

cd /d "C:\Users\User\Desktop\tg outubro\Hiring_Scope_TG2"

if not exist "backups" mkdir backups

set DATA=%date:~-4,4%-%date:~-10,2%-%date:~-7,2%
set ARQUIVO=backups\backup_%DATA%.db

echo Baixando banco de dados...
railway volume files download /app/instance/prestadores.db %ARQUIVO%

echo.
echo ========================================
echo   BACKUP CONCLUIDO!
echo   Arquivo: %ARQUIVO%
echo ========================================
echo.
echo Agora copie o arquivo para o Google Drive!
pause