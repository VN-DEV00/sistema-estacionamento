import os
import cv2
import logging
import time
import re
import smtplib
import random
from email.mime.text import MIMEText  # Importação corrigida para evitar Erro 500
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from dotenv import load_dotenv
from database import Database
from repository import ParkingRepository

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'cria_key_2026')

# Inicializa o Pool de Conexão com o Banco
Database.initialize()

# --- UTILITÁRIOS ---
def validar_placa(placa):
    return re.match(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$", placa.upper())

def login_required_roles(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'usuario' not in session: 
                return redirect(url_for('login'))
            if session.get('tipo_acesso') not in roles:
                flash('Acesso negado!', 'danger')
                return redirect(url_for('menu'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def enviar_email_recuperacao(destinatario, codigo):
    mail_user = os.getenv('MAIL_USER')
    mail_pass = os.getenv('MAIL_PASSWORD').replace(" ", "") # Remove espaços se houver
    
    corpo = f"""
    Olá!
    Recebemos uma solicitação de recuperação de senha.
    Seu código de verificação é: {codigo}
    
    Este código expirará em 15 minutos.
    """
    
    msg = MIMEText(corpo)
    msg['Subject'] = 'Recuperação de Senha - Estacionamento'
    msg['From'] = mail_user
    msg['To'] = destinatario

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(mail_user, mail_pass)
            server.send_message(msg)
        return True
    except Exception as e:
        logging.error(f"Erro no SMTP: {e}")
        return False

# --- LÓGICA DE CÂMERA ---
def gen_frames(camera_id):
    camera = cv2.VideoCapture(camera_id)
    while True:
        success, frame = camera.read()
        if not success: break
        ret, buffer = cv2.imencode('.jpg', cv2.resize(frame, (640, 480)))
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n\r\n')
    camera.release()

@app.route('/video_feed_entrada')
def video_feed_entrada():
    return Response(gen_frames(0), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_saida')
def video_feed_saida():
    return Response(gen_frames(1), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- ROTAS DE AUTENTICAÇÃO ---
@app.route('/')
def index():
    return redirect(url_for('menu')) if 'usuario' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario, senha = request.form.get('usuario'), request.form.get('senha')
        res = ParkingRepository.verificar_login(usuario, senha)
        if res['sucesso']:
            session.update({
                'usuario': res['apelido'] or usuario, 
                'username_real': usuario, 
                'tipo_acesso': res['tipo_acesso']
            })
            if res.get('primeiro_acesso'):
                return redirect(url_for('configurar_perfil'))
            return redirect(url_for('menu'))
        flash('Usuário ou senha incorretos!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        identificador = request.form.get('usuario')
        dados = ParkingRepository.buscar_dados_recuperacao(identificador)
        
        if dados:
            codigo = str(random.randint(100000, 999999))
            if ParkingRepository.salvar_codigo_recuperacao(dados['usuario'], codigo):
                if enviar_email_recuperacao(dados['email'], codigo):
                    session['usuario_recuperacao'] = dados['usuario']
                    flash('Código enviado para seu e-mail!', 'success')
                    return redirect(url_for('validar_codigo_rota'))
        flash('Usuário ou e-mail não encontrado ou erro no servidor.', 'danger')
    return render_template('recuperar_senha.html')

@app.route('/validar-codigo', methods=['GET', 'POST'])
def validar_codigo_rota():
    if 'usuario_recuperacao' not in session: return redirect(url_for('recuperar_senha'))
    if request.method == 'POST':
        if ParkingRepository.validar_codigo_e_redefinir_senha(session['usuario_recuperacao'], request.form.get('codigo'), request.form.get('nova_senha')):
            session.pop('usuario_recuperacao', None)
            flash('Senha alterada! Faça login.', 'success')
            return redirect(url_for('login'))
        flash('Código inválido ou expirado.', 'danger')
    return render_template('validar_codigo.html')

@app.route('/configurar_perfil', methods=['GET', 'POST'])
def configurar_perfil():
    if 'usuario' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        if ParkingRepository.atualizar_perfil_usuario(session.get('username_real'), request.form.get('nova_senha'), request.form.get('apelido'), request.form.get('email')):
            session['usuario'] = request.form.get('apelido')
            flash('Perfil atualizado!', 'success')
            return redirect(url_for('menu'))
    return render_template('configurar_perfil.html')

# --- OPERAÇÕES E CONSULTAS ---
@app.route('/menu')
def menu():
    return render_template('menu.html') if 'usuario' in session else redirect(url_for('login'))

@app.route('/vagas')
@login_required_roles(['Admin', 'Operador'])
def vagas():
    disp, total = ParkingRepository.get_parking_occupancy()
    return render_template('vagas.html', total=total, disponiveis=disp)

@app.route('/monitoramento')
@login_required_roles(['Admin', 'Operador'])
def monitoramento_hub():
    return render_template('monitoramento_hub.html')

@app.route('/monitoramento/view/<tipo>')
@login_required_roles(['Admin', 'Operador'])
def visualizar_cameras(tipo):
    return render_template('visualizar_cameras.html', tipo=tipo)

@app.route('/consultar')
@login_required_roles(['Admin'])
def consultar():
    return render_template('consultar.html')

@app.route('/consultar_placa', methods=['GET', 'POST'])
@login_required_roles(['Admin'])
def consultar_placa():
    dados = []
    if request.method == 'POST':
        dados = ParkingRepository.get_history_by_plate(request.form.get('placa').upper(), request.form.get('de'), request.form.get('ate'))
    return render_template('consultar_placa.html', dados=dados)

@app.route('/consultar_periodo', methods=['GET', 'POST'])
@login_required_roles(['Admin'])
def consultar_periodo():
    dados = []
    if request.method == 'POST':
        dados = ParkingRepository.get_history_by_range(request.form.get('de'), request.form.get('ate'))
    return render_template('consultar_periodo.html', dados=dados)

@app.route('/entrada', methods=['GET', 'POST'])
@login_required_roles(['Admin', 'Operador'])
def entrada():
    if request.method == 'POST':
        sucesso, msg = ParkingRepository.register_entry(request.form.get('placa').upper())
        flash(msg, 'success' if sucesso else 'danger')
    return render_template('entrada.html')

@app.route('/saida', methods=['GET', 'POST'])
@login_required_roles(['Admin', 'Operador'])
def saida():
    if request.method == 'POST':
        sucesso, msg = ParkingRepository.register_exit(request.form.get('placa').upper())
        flash(msg, 'success' if sucesso else 'danger')
    return render_template('saida.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)