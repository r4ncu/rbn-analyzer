import os
import json
import uuid
import threading
import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from analyzer import collect_data, make_charts, make_summary, ALL_BANDS

app = Flask(__name__)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'results')
os.makedirs(RESULTS_DIR, exist_ok=True)

jobs = {}


def run_job(job_id, callsigns, bands, days, lang):
    try:
        jobs[job_id]['status'] = 'running'
        jobs[job_id]['message'] = 'Loading...' if lang == 'en' else 'Загрузка данных...'

        def progress(done, total):
            msg = f'{done}/{total} days' if lang == 'en' else f'Загружено {done}/{total} дней'
            jobs[job_id]['message'] = msg
            jobs[job_id]['progress'] = round(done / total * 100)

        df = collect_data(callsigns, bands, days, progress_cb=progress)
        if df is None:
            jobs[job_id]['status'] = 'done'
            jobs[job_id]['message'] = 'No data found' if lang == 'en' else 'Данные не найдены'
            return

        out = os.path.join(RESULTS_DIR, job_id)
        os.makedirs(out, exist_ok=True)

        df.to_csv(os.path.join(out, 'data.csv'), index=False)
        jobs[job_id]['message'] = 'Generating charts...' if lang == 'en' else 'Генерация графиков...'

        charts = make_charts(df, out, lang=lang)
        summary = make_summary(df, lang=lang)

        with open(os.path.join(out, 'charts.json'), 'w') as f:
            json.dump(charts, f)
        with open(os.path.join(out, 'summary.json'), 'w') as f:
            json.dump(summary, f)

        jobs[job_id]['status'] = 'done'
        jobs[job_id]['message'] = 'Done' if lang == 'en' else 'Готово'
        jobs[job_id]['charts'] = charts
        jobs[job_id]['summary'] = summary
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = str(e)


@app.route('/')
def index():
    return render_template('index.html', bands=ALL_BANDS, cache_bust=datetime.datetime.now().timestamp())


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.json
    callsigns = [c.strip().upper() for c in data.get('callsigns', '').split(',') if c.strip()]
    bands = data.get('bands', ['20m'])
    days = min(int(data.get('days', 365)), 365)
    lang = data.get('lang', 'ru')
    if lang not in ('ru', 'en'):
        lang = 'ru'

    if not callsigns:
        return jsonify({'error': 'Укажите позывной' if lang == 'ru' else 'Enter callsign'}), 400

    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {'status': 'queued', 'message': 'In queue...' if lang == 'en' else 'В очереди...', 'progress': 0}

    t = threading.Thread(target=run_job, args=(job_id, callsigns, bands, days, lang), daemon=True)
    t.start()

    return jsonify({'job_id': job_id})


@app.route('/api/status/<job_id>')
def api_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])


@app.route('/results/<job_id>/<path:filename>')
def serve_result(job_id, filename):
    return send_from_directory(os.path.join(RESULTS_DIR, job_id), filename)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
