from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required, current_user, LoginManager, UserMixin, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import requests
import os

DB_OPTIONS = ["DBPEDIA", "WIKIDATA"]

OPTIONS = ["capital_label", "currency_label",
           "population", "flag_label"]

app = Flask(__name__)

app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    score = db.Column(db.Integer, default=0)

class ReportedQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref(
        'reported_questions', lazy=True))
    question = db.Column(db.String, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

with app.app_context():
    db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 0 = DBpedia; 1 = Wikidata
database = DB_OPTIONS[1]

def get_country_data():
    if database == "DBPEDIA":
        query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX dbp: <http://dbpedia.org/property/>
PREFIX dbc: <http://dbpedia.org/resource/Category:>
PREFIX dct: <http://purl.org/dc/terms/>

SELECT ?country_label ?capital_label ?currency_label ?population ?flag_label ?flag_image ?determination_method_label ?flagStatement WHERE {
  ?country rdf:type dbo:Country;
    dct:subject dbc:Member_states_of_the_United_Nations.
  OPTIONAL { ?country dbp:capital ?capital. }
  OPTIONAL { ?country dbp:currency ?currency. }
  OPTIONAL { ?country dbp:populationEstimate ?population. }
  OPTIONAL { ?country dbo:thumbnail ?flag_image. }
  OPTIONAL { ?country dbo:thumbnail ?flag_image. }
  ?country rdfs:label ?country_label.
  ?capital rdfs:label ?capital_label.
  ?currency rdfs:label ?currency_label.
  ?country rdfs:label ?flag_label, ?determination_method_label, ?flagStatement.
  FILTER(((((((LANG(?country_label)) = "en") && ((LANG(?capital_label)) = "en")) && ((LANG(?currency_label)) = "en")) && ((LANG(?determination_method_label)) = "en")) && ((LANG(?flagStatement)) = "en")) && ((LANG(?flag_label)) = "en"))
}
        """
    if database == "WIKIDATA":
        query = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>

SELECT DISTINCT ?country_label ?capital_label ?currency_label ?population 
                ?flag_label ?flag_image ?determination_method_label ?flagStatement 
		            ?anthem_audio 
WHERE {
  ?country wdt:P31 wd:Q3624078 . 
  FILTER NOT EXISTS { ?country wdt:P31 wd:Q3024240 } 
  FILTER NOT EXISTS { ?country wdt:P31 wd:Q28171280 } 
  OPTIONAL { ?country wdt:P36 ?capital } . 
  OPTIONAL {
    ?country p:P36 ?capitalStatement . 
    ?capitalStatement ps:P36 ?capital .
    ?capitalStatement pq:P459 ?determination_method . 
    ?determination_method rdfs:label ?determination_method_label .
    FILTER (LANG(?determination_method_label) = "en" )
  } . 
  OPTIONAL { ?country wdt:P38 ?currency } . 
  OPTIONAL { ?country wdt:P1082 ?population } . 
  OPTIONAL { 
    ?country p:P41 ?flagStatement . 
    ?flagStatement ps:P41 ?flag_image . 
    ?flagStatement wikibase:rank wikibase:PreferredRank .
    FILTER NOT EXISTS { ?flagStatement pq:P582 ?endTime . } 
  } . 
  OPTIONAL { ?country wdt:P85 ?anthem .
            ?anthem wdt:P51 ?anthem_audio .
  } .
  SERVICE wikibase:label { 
    ?country rdfs:label ?country_label . 
    ?capital rdfs:label ?capital_label . 
    ?currency rdfs:label ?currency_label . 
    ?country rdfs:label ?flag_label .
    bd:serviceParam wikibase:language "en" .
  }
}
        """
        """query = "
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>
        
SELECT DISTINCT ?country_label ?capital_label ?currency_label ?population ?flag_label ?flag_image ?determination_method_label ?flagStatement WHERE {
  ?country wdt:P31 wd:Q3624078.
  FILTER(NOT EXISTS { ?country wdt:P31 wd:Q3024240. })
  FILTER(NOT EXISTS { ?country wdt:P31 wd:Q28171280. })
  OPTIONAL { ?country wdt:P36 ?capital. }
  OPTIONAL {
    ?country p:P36 ?capitalStatement.
    ?capitalStatement ps:P36 ?capital;
      pq:P459 ?determination_method.
    ?determination_method rdfs:label ?determination_method_label.
    FILTER((LANG(?determination_method_label)) = "en")
  }
  OPTIONAL { ?country wdt:P38 ?currency. }
  OPTIONAL { ?country wdt:P1082 ?population. }
  OPTIONAL {
    ?country p:P41 ?flagStatement.
    ?flagStatement ps:P41 ?flag_image;
      wikibase:rank wikibase:PreferredRank.
    FILTER(NOT EXISTS { ?flagStatement pq:P582 ?endTime. })
    FILTER((STR(?flagStatement)) != "http://www.wikidata.org/entity/statement/q750-8E7E59C6-2E4F-4F1B-BCAB-5A96E480FB41")
  }
  SERVICE wikibase:label {
    ?country rdfs:label ?country_label.
    ?capital rdfs:label ?capital_label.
    ?currency rdfs:label ?currency_label.
    ?country rdfs:label ?flag_label.
    bd:serviceParam wikibase:language "en".
  }
}
ORDER BY (?country_label)
        """
    if database == "DBPEDIA":
        url = "https://dbpedia.org/sparql"
    if database == "WIKIDATA":
        url = "https://query.wikidata.org/sparql"
    response = requests.get(url, params={"query": query, "format": "json"})
    data = response.json()["results"]["bindings"]
    for country in data:
        if 'flag_image' in country:
            if not country['flag_image']['value']:
                country['flag_image']['value'] = "./static/images/no_flag.png"
        else:
            country['flag_image'] = {'value': './static/images/no_flag.png'}

        if 'currency_label' in country:
            if not country['currency_label']['value']:
                country['currency_label']['value'] = "nonono"
        else:
            country['currency_label'] = {'value': 'nonono'}

        if 'population' in country:
            if not country['population']['value']:
                country['population']['value'] = "000000"
        else:
            country['population'] = {'value': '000000'}

        if 'capital_label' in country:
            if not country['capital_label']['value']:
                country['capital_label']['value'] = "xxxxxx"
        else:
            country['capital_label'] = {'value': 'xxxxxx'}

        if 'anthem_audio' in country:
            if not country['anthem_audio']['value']:
                country['anthem_audio']['value'] = "no_audio"
        else:
            country['anthem_audio'] = {'value': 'no_audio'}

    filtered_data = [country for country in data if 'determination_method_label' not in country or country['determination_method_label']['value'] != 'de jure']
    country_data = filtered_data
    return country_data

def select_country_data(all_data_int, kind_of_questions_int):
    country_data_int = [(entry["country_label"]["value"], entry[kind_of_questions_int]
                     ["value"], entry["flag_image"]["value"], entry["anthem_audio"]["value"]) for entry in all_data_int]
    return country_data_int

all_data = get_country_data()

def generate_quiz():
    quiz = []
    for _ in range(6):
        kind_of_questions = OPTIONS[random.randint(0, 3)]
        country_data = select_country_data(all_data, kind_of_questions)
        question = random.choice(country_data)
        if kind_of_questions == "flag_label":
            while question[2] == "./static/images/no_flag.png":
                question = random.choice(country_data)

        if kind_of_questions == "currency_label":
            while question[2] == "nonono":
                question = random.choice(country_data)

        if kind_of_questions == "population":
            while question[2] == "000000":
                question = random.choice(country_data)

        if kind_of_questions == "capital":
            while question[2] == "xxxxxx":
                question = random.choice(country_data)

        quiz.append((question, kind_of_questions))
    return quiz

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if "quiz_data" not in session or not session["quiz_data"]:
            session["quiz_data"] = generate_quiz()
        if "score" not in session or not session["score"]:
            session["score"] = 0
        if "before_question_text" not in session or not session["before_question_text"]:
            session["before_question_text"] = ""
        if "user_answers" not in session or not session["user_answers"]:
            session["user_answers"] = []
        return redirect(url_for('quiz'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            login_user(user)
            if "quiz_data" not in session or not session["quiz_data"]:
                session["quiz_data"] = generate_quiz()
            if "score" not in session or not session["score"]:
                session["score"] = 0
            if "before_question_text" not in session or not session["before_question_text"]:
                session["before_question_text"] = ""
            if "user_answers" not in session or not session["user_answers"]:
                session["user_answers"] = []
            return redirect(url_for('quiz'))
        flash('Invalid username or password')
    top_scores = User.query.order_by(User.score.desc()).limit(10).all()
    return render_template('login.html', top_scores=top_scores)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user:
            new_user = User(username=username,
                            password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful, please log in')
            return redirect(url_for('login'))
        flash('Username already exists')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop("quiz_data", [])
    session.pop('user_id', None)
    logout_user()
    return redirect(url_for('login'))

@app.route("/home")
def home():
    if current_user.is_authenticated:
        if "quiz_data" not in session or not session["quiz_data"]:
            session["quiz_data"] = generate_quiz()
        if "score" not in session or not session["score"]:
            session["score"] = 0
        if "before_question_text" not in session or not session["before_question_text"]:
            session["before_question_text"] = ""
        if "user_answers" not in session or not session["user_answers"]:
            session["user_answers"] = []
        return redirect(url_for("quiz"))
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def quiz():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    else:
        if "quiz_data" not in session or not session["quiz_data"]:
            session["quiz_data"] = generate_quiz()
        if "score" not in session or not session["score"]:
            session["score"] = 0
        if "before_question_text" not in session or not session["before_question_text"]:
            session["before_question_text"] = ""
        if "user_answers" not in session or not session["user_answers"]:
            session["user_answers"] = []
    quiz_data = session["quiz_data"]
    score = session["score"]
    before_question_text = session["before_question_text"]
    user_answers = session["user_answers"]
    if request.method == "POST":
        user_answer = request.form.get("answer")
        if (not user_answer and request.form.get("wrong_answers")):
            user_answer = "None"
        ca = quiz_data[0][0]
        user_answers.append(
            (before_question_text, user_answer, ca[1]))
        if user_answer == ca[1]:
            score += 1
        if request.form.get("wrong_answers"):
            reported_question = ReportedQuestion(
                user_id=current_user.id, question=before_question_text, timestamp=datetime.utcnow())
            db.session.add(reported_question)
            db.session.commit()
        quiz_data.pop(0)
        if not quiz_data:
            session["quiz_data"] = quiz_data
            session["score"] = score
            session["before_question_text"] = before_question_text
            session["user_answers"] = user_answers
            return redirect(url_for("result"))
    if not quiz_data:
        quiz_data = generate_quiz()
    (question, correct_answer, flag_image_url, anthem_audio), kind_of_questions = quiz_data[0]
    if anthem_audio == "no_audio":
        anthem_audio = ""
    else:
        anthem_audio = "<audio controls='controls'><source src='" + anthem_audio + "' type='audio/ogg' />seu navegador não suporta HTML5</audio>"
    country_data = select_country_data(all_data, kind_of_questions)
    wrong_options = random.sample(
        [country[1] for country in country_data if (country[1] != correct_answer) and (country[0] != question)], 2)
    options = wrong_options + [correct_answer]
    random.shuffle(options)
    if kind_of_questions == "capital_label":
        question_text = f"What is the capital of {question}?"
    elif kind_of_questions == "currency_label":
        question_text = f"What is the currency of {question}?"
    elif kind_of_questions == "population":
        question_text = f"What is the population of {question}?"
    else:
        question_text = f"Which country does this flag belong to?"
    before_question_text = question_text
    session["quiz_data"] = quiz_data
    session["score"] = score
    session["before_question_text"] = before_question_text
    session["user_answers"] = user_answers
    return render_template("quiz.html", question=question_text, options=options, correct_answer=correct_answer, flag_image_url=flag_image_url, anthem_audio=anthem_audio)

@app.route("/result")
@login_required
def result():
    user = User.query.get(session['user_id'])
    total_score = session["score"]
    user.score += total_score
    db.session.commit()
    result_data = session["user_answers"].copy()
    session.pop("score", 0)
    session.pop("quiz_data", [])
    session.pop("before_question_text", None)
    session.pop("user_answers", [])
    return render_template("result.html", score=total_score, user_answers=result_data)

if __name__ == "__main__":
    app.run(debug=True)
#    app.run(debug=True, port=8080)