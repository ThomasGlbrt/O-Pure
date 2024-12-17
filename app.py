import csv, requests, os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
csv_data, last_update = [], None
static_folder = os.path.join(os.getcwd(), 'static')


def fetch_csv_data(csv_source):
    global csv_data, last_update
    try:
        # Obtenir la taille du fichier CSV en faisant une requête HEAD
        head_response = requests.head(csv_source)
        file_size = int(head_response.headers.get('Content-Length', 0))

        # Calculer l'offset pour récupérer les 168 dernières lignes
        line_size = 30  # Taille approximative d'une ligne en octets
        lines_to_fetch = 168
        start_byte = file_size - (lines_to_fetch * line_size)

        # Effectuer une requête Range pour obtenir les 168 dernières lignes
        headers = {'Range': f'bytes={start_byte}-'}
        response = requests.get(csv_source, headers=headers)

        # Lire le CSV à partir des données récupérées
        lines = response.text.splitlines()
        reader = csv.reader(lines)

        # Stocker les données CSV
        csv_data = [(row[0], float(row[1])) for row in reader if len(row) == 2]
        last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Erreur lors de la récupération des données CSV : {e}")


def get_current_note_value():
    try:
        return round((csv_data[-1][1] / 10) * 5) if csv_data else None
    except Exception as e:
        print(f"Erreur lors du traitement de la dernière note : {e}")
        return None


def calculate_weekly_average():
    try:
        one_week_ago = datetime.now() - timedelta(days=7)
        weekly_values = [value for timestamp, value in csv_data if
                         datetime.strptime(timestamp.split("T")[0], "%Y-%m-%d") >= one_week_ago]
        return round((sum(weekly_values) / len(weekly_values) / 10) * 5) if weekly_values else 0
    except Exception as e:
        print(f"Erreur lors du calcul de la moyenne hebdomadaire : {e}")
        return 0


@app.route('/api/note', methods=['GET'])
def current_note_and_weekly_average():
    format_type = request.args.get('format', default='json', type=str).lower()
    csv_source = "https://storage.googleapis.com/mollusques-caen/data.csv"

    if not csv_data:
        fetch_csv_data(csv_source)

    current_note, weekly_avg = get_current_note_value(), calculate_weekly_average()

    if current_note is not None:
        if format_type == 'json':
            return jsonify({
                "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "current_note": current_note,
                "weekly_avg": weekly_avg,
                "last_update": last_update
            })
        elif format_type == 'txt':
            txt_content = f"La note de l'eau actuellement est à : {current_note}/5\nLa moyenne de la semaine est : {weekly_avg}/5"
            return render_template_string(
                """<html><head><title>Note et Moyenne</title></head><body><h1>Note et Moyenne de l'Eau</h1><pre>{{ content }}</pre></body></html>""",
                content=txt_content)
        return "Format non supporté, veuillez utiliser 'json' ou 'txt'.", 400
    return "Erreur lors du traitement des données", 500


def scheduled_task():
    fetch_csv_data('https://storage.googleapis.com/mollusques-caen/data.csv')


scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_task, 'interval', minutes=1)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True)