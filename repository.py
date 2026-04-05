import os
import logging
import bcrypt
from typing import List, Dict, Any, Tuple
from database import Database
from mysql.connector import Error

class ParkingRepository:

    @staticmethod
    def verificar_login(usuario: str, senha: str) -> dict:
        conn = Database.get_connection()
        if not conn: return {"sucesso": False}
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT senha, apelido, primeiro_acesso, tipo_acesso FROM usuarios WHERE usuario = %s", (usuario,))
                resultado = cursor.fetchone()
                if resultado:
                    hash_banco = resultado['senha'].encode('utf-8')
                    if bcrypt.checkpw(senha.encode('utf-8'), hash_banco):
                        return {
                            "sucesso": True,
                            "primeiro_acesso": resultado['primeiro_acesso'],
                            "apelido": resultado['apelido'],
                            "tipo_acesso": resultado['tipo_acesso']
                        }
            return {"sucesso": False}
        except Error as e:
            logging.error(f"Erro no login: {e}")
            return {"sucesso": False}
        finally:
            conn.close()

    @staticmethod
    def atualizar_perfil_usuario(usuario: str, nova_senha: str, apelido: str, email: str) -> bool:
        conn = Database.get_connection()
        if not conn: return False
        try:
            senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE usuarios 
                    SET senha = %s, apelido = %s, email = %s, primeiro_acesso = FALSE 
                    WHERE usuario = %s
                """, (senha_hash, apelido, email, usuario))
                conn.commit()
                return True
        except Error: return False
        finally: conn.close()

    @staticmethod
    def register_entry(placa: str) -> Tuple[bool, str]:
        conn = Database.get_connection()
        if not conn: return False, "Erro de conexão."
        try:
            conn.start_transaction()
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT COUNT(*) as qtd FROM fluxo WHERE data_saida IS NULL FOR UPDATE")
                if cursor.fetchone()['qtd'] >= int(os.getenv('MAX_VAGAS', 250)):
                    conn.rollback()
                    return False, "Pátio lotado!"
                cursor.execute("INSERT INTO fluxo (placa) VALUES (%s)", (placa.upper(),))
                conn.commit()
                return True, f"Entrada: {placa}"
        except Error: return False, "Erro na entrada."
        finally: conn.close()

    @staticmethod
    def register_exit(placa: str) -> Tuple[bool, str]:
        conn = Database.get_connection()
        if not conn: return False, "Sem conexão."
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE fluxo SET data_saida = NOW() WHERE placa = %s AND data_saida IS NULL", (placa.upper(),))
                conn.commit()
                return (True, "Saída OK") if cursor.rowcount > 0 else (False, "Não encontrado no pátio.")
        except Error: return False, "Erro na saída."
        finally: conn.close()

    @staticmethod
    def get_history_by_plate(placa: str, inicio: str, fim: str) -> List[Dict]:
        conn = Database.get_connection()
        if not conn: return []
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM fluxo WHERE placa = %s AND DATE(data_entrada) BETWEEN %s AND %s ORDER BY data_entrada DESC", (placa, inicio, fim))
                return cursor.fetchall()
        except Error: return []
        finally: conn.close()

    @staticmethod
    def get_history_by_range(inicio: str, fim: str) -> List[Dict]:
        conn = Database.get_connection()
        if not conn: return []
        try:
            with conn.cursor(dictionary=True) as cursor:
                query = """
                    SELECT f.*, v.proprietario, c.nome as categoria FROM fluxo f
                    LEFT JOIN veiculos v ON f.placa = v.placa
                    LEFT JOIN categorias c ON v.id_categoria = c.id_categoria
                    WHERE DATE(f.data_entrada) BETWEEN %s AND %s ORDER BY f.data_entrada DESC
                """
                cursor.execute(query, (inicio, fim))
                return cursor.fetchall()
        except Error: return []
        finally: conn.close()

    @staticmethod
    def get_vehicles_by_profile(tipo: str) -> List[Dict]:
        conn = Database.get_connection()
        if not conn: return []
        try:
            with conn.cursor(dictionary=True) as cursor:
                if tipo == "Visitante":
                    query = """
                        SELECT f.placa, f.data_entrada FROM fluxo f 
                        LEFT JOIN veiculos v ON f.placa = v.placa 
                        WHERE v.placa IS NULL AND f.data_saida IS NULL 
                        ORDER BY f.data_entrada DESC
                    """
                    cursor.execute(query)
                else:
                    query = """
                        SELECT f.placa, v.proprietario, f.data_entrada FROM fluxo f 
                        JOIN veiculos v ON f.placa = v.placa 
                        JOIN categorias c ON v.id_categoria = c.id_categoria 
                        WHERE c.nome = %s AND f.data_saida IS NULL 
                        ORDER BY f.data_entrada DESC
                    """
                    cursor.execute(query, (tipo,))
                return cursor.fetchall()
        except Error: return []
        finally: conn.close()

    @staticmethod
    def get_all_present() -> List[Dict]:
        conn = Database.get_connection()
        if not conn: return []
        try:
            with conn.cursor(dictionary=True) as cursor:
                query = """
                    SELECT f.placa, v.proprietario, f.data_entrada, c.nome as categoria 
                    FROM fluxo f 
                    LEFT JOIN veiculos v ON f.placa = v.placa 
                    LEFT JOIN categorias c ON v.id_categoria = c.id_categoria 
                    WHERE f.data_saida IS NULL
                    ORDER BY f.data_entrada DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Error: return []
        finally: conn.close()

    @staticmethod
    def get_parking_occupancy() -> Tuple[int, int]:
        total = int(os.getenv('MAX_VAGAS', 250))
        conn = Database.get_connection()
        if not conn: return 0, total
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM fluxo WHERE data_saida IS NULL")
                ocupadas = cursor.fetchone()[0]
                disponiveis = total - ocupadas
                return disponiveis, total
        except Error: return 0, total
        finally: conn.close()

    @staticmethod
    def register_vehicle(tipo: str, nome: str, placa: str, veiculo: str) -> Tuple[bool, str]:
        conn = Database.get_connection()
        if not conn: return False, "Erro de conexão."
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id_categoria FROM categorias WHERE nome = %s", (tipo,))
                cat = cursor.fetchone()
                if not cat: return False, "Categoria inválida."
                cursor.execute(
                    "INSERT INTO veiculos (placa, proprietario, id_categoria, tipo_veiculo) VALUES (%s,%s,%s,%s)",
                    (placa.upper(), nome, cat[0], veiculo)
                )
                conn.commit()
                return True, "Veículo cadastrado!"
        except Error as e:
            # CORREÇÃO AQUI: e.errno corrige o problema do Python travar no cadastro!
            return False, "Placa já cadastrada." if e.errno == 1062 else "Erro no cadastro."
        finally: conn.close()