import mysql.connector
import bcrypt
import os
from dotenv import load_dotenv

# Carrega as variáveis do .env
load_dotenv()

# Configuração do banco puxando EXATAMENTE o que está no seu .env
CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)), # <-- O SEGREDO ESTAVA AQUI!
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

usuarios = {
    "Vinicius.Brandao": "Vini.2026",
    "Kelvyn.Sedano": "Kelvyn.2026",
    "Arthur.Terra": "Arthur.2026",
    "Pedro.Lucas": "Pedro.2026",
    "Luiz.Felipe": "Luiz.2026",
    "Ryan.Laeber": "Ryan.2026",
    "Giovanni.Brandao": "Giovanni.2026",
    
}

print(f"🔄 Tentando conectar em {CONFIG['host']}:{CONFIG['port']}...")

try:
    # Conectar ao banco usando o dicionário atualizado
    conn = mysql.connector.connect(**CONFIG)
    cursor = conn.cursor()

    for usuario, senha in usuarios.items():
        # Gerar hash da senha
        hash_senha = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
        hash_senha_str = hash_senha.decode('utf-8')

        # Atualizar no banco
        cursor.execute(
            "UPDATE usuarios SET senha = %s WHERE usuario = %s",
            (hash_senha_str, usuario)
        )
        print(f"✅ Hash atualizado para {usuario}")

    conn.commit()
    print("\n🎉 Todos os usuários atualizados com hash bcrypt na Railway!")

except mysql.connector.Error as err:
    print(f"\n❌ Erro de conexão: {err}")
    print("DICA: Verifique se o seu IP está liberado na Railway ou se os dados do .env mudaram.")

finally:
    if 'cursor' in locals():
        cursor.close()
    if 'conn' in locals() and conn.is_connected():
        conn.close()