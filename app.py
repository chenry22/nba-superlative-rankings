import datetime, random, os
from math import floor

from flask import Flask, jsonify, redirect, render_template, request, url_for
from nba_api.stats.static import players
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, firestore

categories = ['ball', 'aura', 'hot', 'like',
    'scorer', 'defender', 'playmaker', 
    'controversial', 'franchise', 
    'leader', 'teammate'
]
category_prompts = {
    'ball' : 'Who is the better basketball player?',
    'aura' : 'Who has more aura?',
    'hot' : "Who is more attractive?",
    'like' : "Which player do you like more?",
    'scorer' : 'Who is the better scorer?',
    'defender' : 'Who is the better defender?',
    'playmaker' : 'Who is the better playmaker?',
    'controversial' : 'Who is more controversial?',
    'franchise' : "Who would you rather start a franchise with today?",
    'leader' : "Who is a better leader?",
    'teammate' : "Who is a better teammate?"
}

ALL_PLAYERS = players.get_players()
ACTIVE_PLAYERS = players.get_active_players()

load_dotenv()
print(os.environ.get('FIREBASE_PROJECT_ID'))
# cred = credentials.Certificate("serviceKey.json")
cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
        "private_key_id": os.environ.get('PRIVATE_KEY_ID'),
        "private_key": os.environ.get('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
        "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
        "client_id": os.environ.get('CLIENT_ID'),
        "auth_uri": os.environ.get('AUTH_URI'),
        "token_uri": os.environ.get('TOKEN_URI'),
        "auth_provider_x509_cert_url": os.environ.get('AUTH_PROVIDER_X509_CERT_URL'),
        "client_x509_cert_url": os.environ.get('CLIENT_X509_CERT_URL'),
    })
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

def get_headshot_url(player_id):
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

# ELO logic
def expected(rA, rB):
    return 1 / (1 + 10 ** ((rB - rA) / 400))

def update_elo(rA, rB, gpA, gpB, winner_is_A):
    EA = expected(rA, rB)
    EB = expected(rB, rA)

    SA = 1 if winner_is_A else 0
    SB = 1 if not winner_is_A else 0

    # sliding scale, less matchups means voting has greater impact
    maxK = 40
    minK = 16
    scale = 500 # games needeed to half max k value
    KA = floor(minK + (maxK - minK) / (1 + gpA / scale))
    KB = floor(minK + (maxK - minK) / (1 + gpB / scale))

    newEA = rA + KA * (SA - EA)
    newEB = rB + KB * (SB - EB)
    return (newEA, newEB, EA, EB)



def get_or_create(player):
    ref = db.collection("players").document(str(player["id"]))
    doc = ref.get()

    if doc.exists:
        return doc.to_dict()
    else:
        data = { cat : 1500 for cat in categories}
        ref.set(data)
        return data

def load_players(active=True):
    if active:
        p1, p2 = random.sample(ACTIVE_PLAYERS, 2)
    else:
        p1, p2 = random.sample(ALL_PLAYERS, 2)
    p1 = { "name": p1["full_name"], "id": p1["id"], "image": get_headshot_url(p1["id"]) }
    p2 = { "name": p2["full_name"], "id": p2["id"], "image": get_headshot_url(p2["id"]) }
    return (p1, p2)



# ROUTES
@app.route('/')
def home():
    cat = categories[floor(random.random() * len(categories))]
    p1, p2 = load_players()
    return render_template('rank.html', p1=p1, p2=p2, prompt=category_prompts[cat], category=cat)

@app.route('/leaderboard')
def reroute_to_main_leaderboard():
    return redirect('/leaderboard/ball')
@app.route("/leaderboard/<category>")
def leaderboard(category):
    return render_template("leaderboard.html", category=category)

@app.route('/about')
def about():
    return render_template('about.html')


@app.route("/api/leaderboard/<category>")
def leaderboard_api(category):
    last = request.args.get("last")
    query = (db.collection("players")
        .order_by(category, direction=firestore.Query.DESCENDING)
        .limit(50)
    )
    if last:
        last_doc = db.collection("players").document(last).get()
        query = query.start_after(last_doc)

    docs = query.stream()

    ps = []
    last_seen = None
    for doc in docs:
        data = doc.to_dict()
        p = { "id": doc.id, "name": players.find_player_by_id(doc.id)['full_name'], "image": get_headshot_url(doc.id) }
        for k, v in data.items(): p[k] = v

        ps.append(p)
        last_seen = doc.id

    return jsonify({
        "players": ps,
        "last": last_seen
    })


# endpoints to load data
@app.route("/new_matchup")
def matchup():
    active = request.args.get("active")
    cat = categories[floor(random.random() * len(categories))]
    p1, p2 = load_players(active)
    return jsonify({"p1": p1, "p2": p2, "prompt": category_prompts[cat], "category": cat})

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    p1 = data["p1"]
    p2 = data["p2"]
    winner_id = data["winner"]
    cat = data["cat"]

    p1_db = get_or_create(p1)
    p2_db = get_or_create(p2)

    r1, r2, gp1, gp2 = p1_db[cat], p2_db[cat] , p1_db.get('matchups', 0), p2_db.get('matchups', 0)
    if r1 is None: r1 = 1500
    if r2 is None: r2 = 1500

    winner_is_p1 = (str(winner_id) == str(p1["id"]))
    new_r1, new_r2, E1, E2 = update_elo(r1, r2, gp1, gp2, winner_is_p1)

    db.collection("players").document(str(p1["id"])).update({
        cat : new_r1, 
        'matchups' : p1_db.get('matchups', 0) + 1
    })
    db.collection("players").document(str(p2["id"])).update({
        cat : new_r2,
        'matchups' : p2_db.get('matchups', 0) + 1
    })

    # ig we can keep track of matchups
    db.collection("matchups").add({
        'winner' : int(winner_id),
        'loser' : p1['id'] if int(winner_id) == p2['id'] else p2['id'],
        'change' : abs(r1 - new_r1),
        'time' : datetime.datetime.now()
    })

    return jsonify({
        "p1": {**p1, "before": r1, "after": new_r1, "expected": E1},
        "p2": {**p2, "before": r2, "after": new_r2, "expected": E2},
        "winner": winner_id
    })

if __name__ == '__main__':
    app.run(debug=True)