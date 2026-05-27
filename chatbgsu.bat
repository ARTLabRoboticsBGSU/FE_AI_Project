@echo off
cd /d C:\Users\webapp\.conda\chat_bgsu
C:\Users\webapp\.conda\envs\chatbgsu\python.exe -m streamlit run chatgpt.py --server.address chatbgsu.fsb.miamioh.edu --server.port 443 --server.sslCertFile C:\Users\webapp\.conda\chat_bgsu\ssl\chatbgsu.pem --server.sslKeyFile C:\Users\webapp\.conda\chat_bgsu\ssl\chatbgsupriv.key
pause