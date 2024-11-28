from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import requests
import os
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from pymongo import MongoClient
import re

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'uma_chave_secreta_padrao')  # Adicione uma chave secreta para a sessão

# Configurações da API TMDB
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
PROFILE_BASE_URL = "https://image.tmdb.org/t/p/w185"

# Conexão com o MongoDB
MONGODB_URI = os.getenv('MONGODB_URI')
# Remova os caracteres < e > da string de conexão
MONGODB_URI = MONGODB_URI.replace('<', '').replace('>', '')
client = MongoClient(MONGODB_URI)
db = client['projetotmdb']  # Especifique o nome do banco de dados aqui
users_collection = db['users']  # Nome da coleção

# Verifica a conexão com o MongoDB
try:
    # O comando ping é usado para verificar a conexão
    client.admin.command('ping')
    print("Conexão com o MongoDB estabelecida com sucesso!")
except Exception as e:
    print(f"Erro ao conectar ao MongoDB: {e}")
    # Você pode decidir se quer encerrar o aplicativo aqui ou continuar com funcionalidade limitada
    # import sys
    # sys.exit(1)  # Descomente esta linha se quiser encerrar o aplicativo em caso de falha na conexão

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_movies(endpoint, page=1):
    """Função auxiliar para buscar filmes da API"""
    try:
        response = requests.get(
            f"{BASE_URL}/{endpoint}",
            params={
                "api_key": TMDB_API_KEY,
                "language": "pt-BR",
                "page": page
            }
        )
        return response.json()
    except requests.exceptions.RequestException:
        return None
    
@app.route('/')
def home():
    trending_movies = get_movies("trending/movie/week")
    popular_movies = get_movies("movie/popular")
    upcoming_movies = get_movies("movie/upcoming")
    new_releases = get_movies("movie/now_playing")
    recommended_movies = get_movies("movie/top_rated")  # Adicionando filmes recomendados
    
    if trending_movies and popular_movies and upcoming_movies and new_releases and recommended_movies:
        trending = trending_movies.get('results', [])[:10]
        popular = popular_movies.get('results', [])[:10]
        upcoming = upcoming_movies.get('results', [])[:10]
        new = new_releases.get('results', [])[:10]
        recommended = recommended_movies.get('results', [])[:10]  # Pegando os 10 primeiros filmes recomendados
        return render_template('index.html', 
                               trending_movies=trending, 
                               popular_movies=popular, 
                               upcoming_movies=upcoming,
                               new_releases=new,
                               recommended_movies=recommended,  # Adicionando filmes recomendados ao contexto
                               poster_base_url=POSTER_BASE_URL)
    return "Erro ao carregar filmes", 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validações básicas
        if not name or not email or not password or not confirm_password:
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('As senhas não coincidem.', 'error')
            return redirect(url_for('register'))

        # Verificar se o usuário já existe
        existing_user = users_collection.find_one({'email': email})
        if existing_user:
            flash('Email já cadastrado. Por favor, use outro email.', 'error')
            return redirect(url_for('register'))

        # Criar um novo usuário
        hashed_password = generate_password_hash(password)
        new_user = {
            'name': name,
            'email': email,
            'password': hashed_password
        }

        # Inserir o novo usuário no banco de dados
        try:
            result = users_collection.insert_one(new_user)
            if result.inserted_id:
                print(f"Novo usuário inserido com ID: {result.inserted_id}")
                flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
                return redirect(url_for('login'))
            else:
                print("Falha ao inserir novo usuário")
                flash('Erro ao cadastrar. Por favor, tente novamente.', 'error')
        except Exception as e:
            print(f"Erro ao inserir usuário no banco de dados: {e}")
            flash('Erro ao cadastrar. Por favor, tente novamente.', 'error')

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = users_collection.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            session['user_email'] = email
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        else:
            flash('Email ou senha inválidos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.pop('user_email', None)
    flash('Você foi desconectado com sucesso.', 'success')
    return redirect(url_for('home'))

@app.route('/new_releases')
def get_new_releases():
    new_releases = get_movies("movie/now_playing")
    if new_releases:
        return jsonify(new_releases.get('results', [])[:10])
    return jsonify({"error": "Erro ao carregar lançamentos"}), 500

@app.route('/trending')
def get_trending():
    trending_movies = get_movies("trending/movie/week")
    if trending_movies:
        return jsonify(trending_movies.get('results', [])[:10])
    return jsonify({"error": "Erro ao carregar filmes em alta"}), 500

@app.route('/recommended')
def get_recommended():
    recommended_movies = get_movies("movie/top_rated")
    if recommended_movies:
        return jsonify(recommended_movies.get('results', [])[:10])
    return jsonify({"error": "Erro ao carregar filmes recomendados"}), 500

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_email = session['user_email']
    user = users_collection.find_one({'email': user_email})
    
    if request.method == 'POST':
        # Atualização da senha
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        
        if not check_password_hash(user['password'], current_password):
            flash('Senha atual incorreta.', 'error')
        else:
            hashed_password = generate_password_hash(new_password)
            users_collection.update_one(
                {'email': user_email},
                {'$set': {'password': hashed_password}}
            )
            flash('Senha atualizada com sucesso!', 'success')
    
    return render_template('profile.html', user=user)


@app.route('/search')
def search():
    query = request.args.get('query', '')
    if query:
        try:
            response = requests.get(
                f"{BASE_URL}/search/movie",
                params={
                    "api_key": TMDB_API_KEY,
                    "language": "pt-BR",
                    "query": query
                }
            )
            search_results = response.json()
            movies = search_results.get('results', [])
            return render_template('search.html', movies=movies, query=query, poster_base_url=POSTER_BASE_URL)
        except requests.exceptions.RequestException:
            return "Erro na busca", 500
    return render_template('search.html', movies=[], query='', poster_base_url=POSTER_BASE_URL)

@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    try:
        response = requests.get(
            f"{BASE_URL}/movie/{movie_id}",
            params={
                "api_key": TMDB_API_KEY,
                "language": "pt-BR",
                "append_to_response": "credits,recommendations"
            }
        )
        movie = response.json()
        
        # Adiciona a URL da foto do perfil para cada membro do elenco
        for cast_member in movie['credits']['cast']:
            if cast_member['profile_path']:
                cast_member['profile_url'] = f"{PROFILE_BASE_URL}{cast_member['profile_path']}"
            else:
                cast_member['profile_url'] = None
        
        # Obter filmes recomendados
        recommended_movies = movie['recommendations']['results'][:10]
        
        return render_template('movie_detail.html', 
                               movie=movie, 
                               recommended_movies=recommended_movies,
                               poster_base_url=POSTER_BASE_URL, 
                               profile_base_url=PROFILE_BASE_URL)
    except requests.exceptions.RequestException:
        return "Erro ao carregar detalhes do filme", 500

@app.route('/movie/<int:movie_id>/trailer')
def get_movie_trailer(movie_id):
    try:
        response = requests.get(
            f"{BASE_URL}/movie/{movie_id}/videos",
            params={
                "api_key": TMDB_API_KEY,
                "language": "pt-BR"
            }
        )
        videos = response.json()
        trailers = [video for video in videos.get('results', []) if video['type'] == 'Trailer']
        
        if trailers:
            return jsonify({"trailer_key": trailers[0]['key']})
        else:
            return jsonify({"error": "Nenhum trailer encontrado"}), 404
    except requests.exceptions.RequestException:
        return jsonify({"error": "Erro ao buscar o trailer"}), 500

@app.route('/watchlist/<int:movie_id>', methods=['POST'])
@login_required
def toggle_watchlist(movie_id):
    user_email = session['user_email']
    user = users_collection.find_one({'email': user_email})
    
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404
    
    watchlist = user.get('watchlist', [])
    
    if movie_id in watchlist:
        watchlist.remove(movie_id)
        message = "Filme removido da watchlist"
    else:
        watchlist.append(movie_id)
        message = "Filme adicionado à watchlist"
    
    users_collection.update_one({'email': user_email}, {'$set': {'watchlist': watchlist}})
    return jsonify({"message": message, "in_watchlist": movie_id in watchlist})

@app.route('/watchlist')
@login_required
def view_watchlist():
    user_email = session['user_email']
    user = users_collection.find_one({'email': user_email})
    
    if not user:
        return "Usuário não encontrado", 404
    
    watchlist = user.get('watchlist', [])
    movies = []
    for movie_id in watchlist:
        try:
            response = requests.get(
                f"{BASE_URL}/movie/{movie_id}",
                params={
                    "api_key": TMDB_API_KEY,
                    "language": "pt-BR"
                }
            )
            movie = response.json()
            movies.append(movie)
        except requests.exceptions.RequestException:
            continue
    return render_template('watchlist.html', movies=movies, poster_base_url=POSTER_BASE_URL)

@app.route('/movie/<int:movie_id>/platforms')
def get_movie_platforms(movie_id):
    try:
        response = requests.get(
            f"{BASE_URL}/movie/{movie_id}/watch/providers",
            params={
                "api_key": TMDB_API_KEY
            }
        )
        providers = response.json()
        
        # Filtrando para obter apenas os provedores no Brasil
        br_providers = providers.get('results', {}).get('BR', {})
        
        platforms = {
            'flatrate': br_providers.get('flatrate', []),
            'rent': br_providers.get('rent', []),
            'buy': br_providers.get('buy', [])
        }
        
        return jsonify(platforms)
    except requests.exceptions.RequestException:
        return jsonify({"error": "Erro ao buscar as plataformas"}), 500

@app.route('/tv')
def get_tv_series():
    try:
        response = requests.get(
            f"{BASE_URL}/tv/popular",
            params={
                "api_key": TMDB_API_KEY,
                "language": "pt-BR",
                "page": 1
            }
        )
        tv_series = response.json()
        return jsonify(tv_series.get('results', [])[:10])
    except requests.exceptions.RequestException:
        return jsonify({"error": "Erro ao buscar séries de TV"}), 500

if __name__ == '__main__':
    app.run(debug=True)
