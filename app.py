import csv ,io, json, requests, os, pytz
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
csv_data, last_update = [], None
queries_enabled = True  # Contrôle d'état des requêtes
past_queries = []  # Liste des requêtes passées (limite à 3)
static_folder = os.path.join(os.getcwd(), 'static')


# --- Récupérer les données du CSV ---
def fetch_csv_data(csv_source):
    global csv_data, last_update
    try:
        head_response = requests.head(csv_source)
        file_size = int(head_response.headers.get('Content-Length', 0))
        line_size = 30  # Taille approximative d'une ligne
        lines_to_fetch = 168
        start_byte = file_size - (lines_to_fetch * line_size)

        headers = {'Range': f'bytes={start_byte}-'}
        response = requests.get(csv_source, headers=headers)
        lines = response.text.splitlines()
        reader = csv.reader(lines)

        csv_data = [(row[0], float(row[1])) for row in reader if len(row) == 2]
        last_update = datetime.now(pytz.timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Erreur lors de la récupération des données CSV : {e}")


# --- Calculer les statistiques ---
def get_current_note_value():
    try:
        return round((csv_data[-1][1] / 10) * 5) if csv_data else None
    except Exception as e:
        print(f"Erreur : {e}")
        return None


def calculate_weekly_average():
    try:
        one_week_ago = datetime.now() - timedelta(days=7)
        weekly_values = [value for timestamp, value in csv_data if
                         datetime.strptime(timestamp.split("T")[0], "%Y-%m-%d") >= one_week_ago]
        return round((sum(weekly_values) / len(weekly_values) / 10) * 5) if weekly_values else 0
    except Exception as e:
        print(f"Erreur : {e}")
        return 0


# --- Ajouter une requête automatique ---
def append_scheduled_query():
    if queries_enabled:
        fetch_csv_data('https://storage.googleapis.com/mollusques-caen/data.csv')

        current_note = get_current_note_value()
        weekly_avg = calculate_weekly_average()
        now = datetime.now(pytz.timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")

        json_data = json.dumps({
            "current_time": now,
            "current_note": current_note,
            "weekly_avg": weekly_avg,
            #"last_update": last_update
        }, indent=4)

        # Ajouter dans la liste et limiter à 3 éléments
        past_queries.append({"format": "json", "data": json_data})
        if len(past_queries) > 3:
            past_queries.pop(0)


# --- Routes ---
@app.route('/')
def home():
    if not csv_data:
        fetch_csv_data('https://storage.googleapis.com/mollusques-caen/data.csv')

    current_note = get_current_note_value()
    weekly_avg = calculate_weekly_average()

    return render_template_string("""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Gestion des Requêtes</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            setInterval(function() {
                window.location.reload();
            }, 300000);  // Actualisation toutes les 5 minutes
        </script>
    </head>
    <body class="bg-gray-100 text-gray-900">
        <div class="p-8">
            <h1 class="text-3xl font-semibold text-center mb-6">Gestion des Requêtes</h1>
            <div class="text-center mb-4">
                <form action="/toggle" method="post">
                    <button type="submit" class="px-4 py-2 rounded {% if queries_enabled %}bg-red-500 hover:bg-red-700{% else %}bg-green-500 hover:bg-green-700{% endif %} text-white">
                        {% if queries_enabled %} Désactiver {% else %} Activer {% endif %} les Requêtes
                    </button>
                </form>
            </div>
            <div class="bg-white p-4 rounded shadow mb-4">
                <h2 class="text-xl font-semibold">Note actuelle : {{ current_note }}/5</h2>
                <h2 class="text-xl font-semibold mt-2">Moyenne Hebdomadaire : {{ weekly_avg }}/5</h2>
                <p class="text-sm text-gray-600 mt-2">Dernière mise à jour : {{ last_update }}</p>
            </div>
            <h2 class="text-2xl font-semibold mb-4">3 Dernières Requêtes</h2>
            <div class="grid grid-cols-1 gap-4">
                {% for query in past_queries[::-1] %}
                <div class="p-4 rounded {% if query.format == 'json' %}bg-gray-800 text-white{% else %}bg-white{% endif %}">
                    <pre>{{ query.data }}</pre>
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    """, queries_enabled=queries_enabled, current_note=current_note, weekly_avg=weekly_avg,
       last_update=last_update, past_queries=past_queries)


@app.route('/toggle', methods=['POST'])
def toggle_queries():
    global queries_enabled
    queries_enabled = not queries_enabled
    return redirect('/')


@app.route('/api/note', methods=['GET'])
def current_note_and_weekly_average():
    format_type = request.args.get('format', default='json', type=str).lower()
    if queries_enabled:
        current_note, weekly_avg = get_current_note_value(), calculate_weekly_average()
        now = datetime.now(pytz.timezone('Europe/Paris')).strftime("%Y-%m-%d %H:%M:%S")

        if format_type == 'json':
            data = {
                "current_time": now,
                "current_note": current_note,
                "weekly_avg": weekly_avg,
                #"last_update": last_update
            }
            json_data = json.dumps(data, indent=4)
            past_queries.append({"format": "json", "data": json_data})
            return jsonify(data)
        elif format_type == 'txt':
            txt_content = f"Note actuelle : {current_note}/5\nMoyenne Hebdomadaire : {weekly_avg}/5"
            past_queries.append({"format": "txt", "data": txt_content})
            return txt_content, 200, {'Content-Type': 'text/plain'}
    return "Requêtes désactivées", 403


# --- Tâche planifiée ---
def scheduled_task():
    append_scheduled_query()


scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_task, 'interval', hours=1)
scheduler.start()

# --- Initialisation avec requêtes par défaut ---
fetch_csv_data('https://storage.googleapis.com/mollusques-caen/data.csv')
append_scheduled_query()  # Première requête ajoutée

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
