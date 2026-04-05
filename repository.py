import os
import bcrypt
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from database import Database
from mysql.connector import Error

class ParkingRepository:

    @staticmethod
    def verificar_login(usuario: str, senha: str) -> dict:
        conn = Database.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT senha, apelido, primeiro_acesso, tipo_acesso FROM usuarios WHERE usuario = %s", (usuario,))
                res = cursor.fetchone()
                if res and bcrypt.checkpw(senha.encode('utf-8'), res['senha'].encode('utf-8')):
                    return {"sucesso": True, "primeiro_acesso": res['primeiro_acesso'], "apelido": res['apelido'], "tipo_acesso": res['tipo_acesso']}
            return {"sucesso": False}
        except Error: return {"sucesso": False}
        finally: conn.close()

    @staticmethod
    def buscar_dados_recuperacao(identificador: str) -> dict:
        conn = Database.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # Busca por usuário OU e-mail
                cursor.execute("SELECT usuario, email FROM usuarios WHERE usuario = %s OR email = %s", (identificador, identificador))
                return cursor.fetchone()
        except Error: return None
        finally: conn.close()

    @staticmethod
    def salvar_codigo_recuperacao(usuario: str, codigo: str) -> bool:
        conn = Database.get_connection()
        exp = datetime.now() + timedelta(minutes=15)
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM recuperacao_senha WHERE usuario = %s", (usuario,))
                cursor.execute("INSERT INTO recuperacao_senha (usuario, codigo, expiracao) VALUES (%s, %s, %s)", (usuario, codigo, exp))
                conn.commit()
                return True
        except Error: return False
        finally: conn.close()

    @staticmethod
    def validar_codigo_e_redefinir_senha(usuario: str, codigo: str, nova_senha: str) -> bool:
        conn = Database.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM recuperacao_senha WHERE usuario = %s AND codigo = %s AND expiracao > NOW()", (usuario, codigo))
                if not cursor.fetchone(): return False
                hash_nova = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute("UPDATE usuarios SET senha = %s WHERE usuario = %s", (hash_nova, usuario))
                cursor.execute("DELETE FROM recuperacao_senha WHERE usuario = %s", (usuario,))
                conn.commit()
                return True
        except Error: return False
        finally: conn.close()

    @staticmethod
    def get_parking_occupancy() -> Tuple[int, int]:
        total = int(os.getenv('MAX_VAGAS', 250))
        conn = Database.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM fluxo WHERE data_saida IS NULL")
                ocupadas = cursor.fetchone()[0]
                return total - ocupadas, total
        except Error: return 0, total
        finally: conn.close()

    @staticmethod
    def register_entry(placa: str) -> Tuple[bool, str]:
        conn = Database.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO fluxo (placa) VALUES (%s)", (placa,))
                conn.commit()
                return True, f"Entrada registrada: {placa}"
        except Error: return False, "Erro ao registrar entrada."
        finally: conn.close()

    @staticmethod
    def register_exit(placa: str) -> Tuple[bool, str]:
        conn = Database.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE fluxo SET data_saida = NOW() WHERE placa = %s AND data_saida IS NULL", (placa,))
                conn.commit()
                return (True, "Saída registrada") if cursor.rowcount > 0 else (False, "Veículo não encontrado")
        except Error: return False, "Erro ao registrar saída."
        finally: conn.close()

    @staticmethod
    def get_history_by_plate(placa: str, inicio: str, fim: str) -> List[Dict]:
        conn = Database.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM fluxo WHERE placa = %s AND DATE(data_entrada) BETWEEN %s AND %s ORDER BY data_entrada DESC", (placa, inicio, fim))
                return cursor.fetchall()
        except Error: return []
        finally: conn.close()

    @staticmethod
    def get_history_by_range(inicio: str, fim: str) -> List[Dict]:
        conn = Database.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                query = "SELECT f.*, v.proprietario FROM fluxo f LEFT JOIN veiculos v ON f.placa = v.placa WHERE DATE(f.data_entrada) BETWEEN %s AND %s ORDER BY f.data_entrada DESC"
                cursor.execute(query, (inicio, fim))
                return cursor.fetchall()
        except Error: return []
        finally: conn.close()
    
    @staticmethod
    def atualizar_perfil_usuario(usuario, senha, apelido, email):
        conn = Database.get_connection()
        hash_s = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE usuarios SET senha=%s, apelido=%s, email=%s, primeiro_acesso=FALSE WHERE usuario=%s", (hash_s, apelido, email, usuario))
                conn.commit()
                return True
        except Error: return False
        finally: conn.close()