import os
import logging
from typing import Optional
from mysql.connector import pooling, Error
from dotenv import load_dotenv

load_dotenv()

class Database:
    _pool: Optional[pooling.MySQLConnectionPool] = None

    @classmethod
    def initialize(cls) -> None:
        if cls._pool is not None:
            return
            
        try:
            host = os.getenv('DB_HOST')
            port = int(os.getenv('DB_PORT', 3306)) # CORREÇÃO: Porta como número!
            user = os.getenv('DB_USER')
            password = os.getenv('DB_PASSWORD')
            database = os.getenv('DB_NAME')

            logging.info(f"Tentando conectar ao host: {host} na porta: {port}")

            cls._pool = pooling.MySQLConnectionPool(
                pool_name="parking_pool",
                pool_size=10,
                pool_reset_session=True,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                connection_timeout=10,
                autocommit=True
            )
            logging.info("✅ Pool de conexões inicializado com sucesso.")
            
        except Error as e:
            logging.critical(f"❌ Falha na inicialização do Pool: {e}")
            raise e
        except Exception as ex:
            logging.critical(f"❌ Erro inesperado: {ex}")
            raise ex

    @classmethod
    def get_connection(cls):
        if not cls._pool:
            cls.initialize()
        try:
            return cls._pool.get_connection()
        except Error as e:
            logging.error(f"❌ Erro ao obter conexão: {e}")
            return None