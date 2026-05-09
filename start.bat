@echo off
title ���ݼ���ɸ���� - ������...

echo ==========================================
echo   ���ݼ���ɸ����
echo ==========================================
echo.

:: ���� conda data ���� + ���� HF ����
set HF_ENDPOINT=https://hf-mirror.com
set CONDA_ENV=data

echo [1/2] ������� (�˿� 8000, conda: %CONDA_ENV%)...
start "��� API ����" cmd /k "conda activate %CONDA_ENV% && set HF_ENDPOINT=https://hf-mirror.com && cd /d %~dp0backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [2/2] ����ǰ�� (�˿� 5173)...
start "ǰ�˽���" cmd /k "cd /d %~dp0frontend && npx vite --host"

echo.
echo ==========================================
echo   ������ɣ�
echo   ǰ��: http://localhost:5173
echo   API�ĵ�: http://localhost:8000/docs
echo ==========================================
echo.
echo   �رձ����ڲ�Ӱ��ǰ������С�
echo   Ҫֹͣ������رպ�˺�ǰ�˸��ԵĴ��ڡ�
echo.

timeout /t 3 >/dev/null
exit
