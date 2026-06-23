import datetime
import requests
import zipfile
import io
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
from concurrent.futures import ThreadPoolExecutor

# --- КОНФИГУРАЦИЯ ---
CALLSIGNS = ["R4NCU"]
BANDS = ["20m", "15m", "10m", "40m"]
DAYS_TO_ANALYZE = 365
MAX_WORKERS = 10
OUTPUT_DIR = "rbn_results"

RBN_URL = "https://data.reversebeacon.net/rbn_history/{date}.zip"

def setup_environment():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sns.set_theme(style="whitegrid")

def download_day(date_str, callsign, band):
    url = RBN_URL.format(date=date_str)
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_filename = f"{date_str}.csv"
                if csv_filename in z.namelist():
                    with z.open(csv_filename) as f:
                        df = pd.read_csv(f, low_memory=False)
                        filtered = df[(df['callsign'] == callsign) & (df['band'] == band)]
                        return filtered
    except Exception as e:
        print(f"  Ошибка {date_str} ({callsign}/{band}): {e}")
    return None

def collect_data():
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=DAYS_TO_ANALYZE)
    dates = [(start_date + datetime.timedelta(days=i)).strftime("%Y%m%d")
             for i in range((end_date - start_date).days + 1)]

    all_frames = []
    total_tasks = len(CALLSIGNS) * len(BANDS) * len(dates)
    done = 0

    for callsign in CALLSIGNS:
        for band in BANDS:
            print(f"Загрузка {callsign} / {band} ...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(download_day, d, callsign, band): d for d in dates}
                for future in futures:
                    res = future.result()
                    if res is not None and not res.empty:
                        res = res.copy()
                        res['callsign_spotter'] = callsign
                        all_frames.append(res)
                    done += 1
                    if done % 50 == 0 or done == total_tasks:
                        print(f"  Прогресс: {done}/{total_tasks}")

    if not all_frames:
        return None
    final = pd.concat(all_frames, ignore_index=True)
    final['date'] = pd.to_datetime(final['date'])
    return final

def get_season(m):
    if m in [12, 1, 2]: return 'Winter'
    if m in [3, 4, 5]: return 'Spring'
    if m in [6, 7, 8]: return 'Summer'
    return 'Autumn'

def generate_charts(df):
    print("Генерация графиков...")
    band = df['band'].iloc[0] if df['band'].nunique() == 1 else "all"
    tags = []

    charts = {}

    # --- 1. Топ-20 стран ---
    fig, ax = plt.subplots(figsize=(12, 8))
    country_stats = df['dx_pfx'].value_counts().head(20)
    sns.barplot(x=country_stats.values, y=country_stats.index, hue=country_stats.index, palette='viridis', legend=False, ax=ax)
    ax.set_title(f'Топ-20 стран | {band}')
    path = f'stats_countries_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['countries'] = path
    country_stats.to_csv(os.path.join(OUTPUT_DIR, f'stats_countries_{band}.csv'))
    tags.append(('Топ-20 стран', path, country_stats.to_frame('count').to_html()))

    # --- 2. Топ-20 позывных ---
    fig, ax = plt.subplots(figsize=(12, 8))
    cs_stats = df['dx'].value_counts().head(20)
    sns.barplot(x=cs_stats.values, y=cs_stats.index, hue=cs_stats.index, palette='magma', legend=False, ax=ax)
    ax.set_title(f'Топ-20 позывных | {band}')
    path = f'stats_callsigns_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['callsigns'] = path
    tags.append(('Топ-20 позывных', path, cs_stats.to_frame('count').to_html()))

    # --- 3. Активность по часам ---
    df['hour'] = df['date'].dt.hour
    fig, ax = plt.subplots(figsize=(12, 6))
    hour_stats = df['hour'].value_counts().sort_index()
    sns.lineplot(x=hour_stats.index, y=hour_stats.values, marker='o', color='blue', ax=ax)
    ax.set_title(f'Активность по часам UTC | {band}')
    ax.set_xticks(range(0, 24))
    ax.set_xlabel('Час')
    ax.set_ylabel('Спотов')
    path = f'stats_hours_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['hours'] = path
    tags.append(('Активность по часам', path, hour_stats.to_frame('count').to_html()))

    # --- 4. Дни недели ---
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_ru = {'Monday': 'Пн', 'Tuesday': 'Вт', 'Wednesday': 'Ср', 'Thursday': 'Чт', 'Friday': 'Пт', 'Saturday': 'Сб', 'Sunday': 'Вс'}
    df['day_name'] = df['date'].dt.day_name()
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.countplot(data=df, x='day_name', order=day_order, hue='day_name', palette='YlGnBu', legend=False, ax=ax)
    ax.set_title(f'Активность по дням недели | {band}')
    ax.set_xticklabels([day_ru.get(d, d) for d in day_order])
    path = f'stats_days_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['days'] = path
    day_counts = df['day_name'].value_counts().reindex(day_order)
    tags.append(('Дни недели', path, day_counts.to_frame('count').to_html()))

    # --- 5. Месяцы ---
    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    df['month'] = df['date'].dt.month_name()
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.countplot(data=df, x='month', order=month_order, hue='month', palette='coolwarm', legend=False, ax=ax)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45)
    ax.set_title(f'Активность по месяцам | {band}')
    path = f'stats_months_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['months'] = path
    month_counts = df['month'].value_counts().reindex(month_order)
    tags.append(('Месяцы', path, month_counts.to_frame('count').to_html()))

    # --- 6. Сезоны ---
    df['season'] = df['date'].dt.month.map(get_season)
    fig, ax = plt.subplots(figsize=(8, 8))
    season_counts = df['season'].value_counts()
    ax.pie(season_counts, labels=season_counts.index, autopct='%1.1f%%', colors=sns.color_palette('pastel'))
    ax.set_title(f'Сезоны | {band}')
    path = f'stats_seasons_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['seasons'] = path
    tags.append(('Сезоны', path, season_counts.to_frame('count').to_html()))

    # --- 7. HEATMAP: часы × дни недели ---
    pivot1 = df.groupby(['day_name', 'hour']).size().unstack(fill_value=0)
    pivot1 = pivot1.reindex(day_order)
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(pivot1, cmap='YlOrRd', ax=ax, cbar_kws={'label': 'Кол-во спотов'})
    ax.set_title(f'Heatmap: День недели × Час UTC | {band}')
    ax.set_ylabel('')
    ax.set_xlabel('Час UTC')
    path = f'heatmap_dow_hour_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['heatmap_dow_hour'] = path
    tags.append(('Heatmap день×час', path, pivot1.to_html()))

    # --- 8. HEATMAP: часы × месяцы ---
    pivot2 = df.groupby(['month', 'hour']).size().unstack(fill_value=0)
    pivot2 = pivot2.reindex(month_order)
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(pivot2, cmap='YlGnBu', ax=ax, cbar_kws={'label': 'Кол-во спотов'})
    ax.set_title(f'Heatmap: Месяц × Час UTC | {band}')
    ax.set_ylabel('')
    ax.set_xlabel('Час UTC')
    path = f'heatmap_month_hour_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    charts['heatmap_month_hour'] = path
    tags.append(('Heatmap месяц×час', path, pivot2.to_html()))

    return tags

def generate_comparison(df_current, df_previous):
    print("Сравнение с прошлым годом...")
    tags = []
    band = df_current['band'].iloc[0] if df_current['band'].nunique() == 1 else "all"

    cur_total = len(df_current)
    prev_total = len(df_previous)

    # Сравнение по месяцам
    month_order = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    cur_months = df_current['date'].dt.month_name().value_counts().reindex(month_order, fill_value=0)
    prev_months = df_previous['date'].dt.month_name().value_counts().reindex(month_order, fill_value=0)

    comparison = pd.DataFrame({'Текущий год': cur_months, 'Прошлый год': prev_months})
    comparison['Изменение %'] = ((comparison['Текущий год'] - comparison['Прошлый год']) / comparison['Прошлый год'].replace(0, 1) * 100).round(1)

    fig, ax = plt.subplots(figsize=(14, 7))
    x = range(len(month_order))
    width = 0.35
    ax.bar([i - width/2 for i in x], comparison['Текущий год'], width, label='Текущий год', color='#4C72B0')
    ax.bar([i + width/2 for i in x], comparison['Прошлый год'], width, label='Прошлый год', color='#DD8452')
    ax.set_xticks(list(x))
    ax.set_xticklabels([m[:3] for m in month_order])
    ax.set_title(f'Сравнение по месяцам | {band}')
    ax.set_ylabel('Кол-во спотов')
    ax.legend()
    path = f'comparison_months_{band}.png'
    fig.savefig(os.path.join(OUTPUT_DIR, path), bbox_inches='tight')
    plt.close(fig)
    tags.append(('Сравнение по месяцам', path, comparison.to_html()))

    # Сводка
    summary = pd.DataFrame({
        'Метрика': ['Всего спотов', 'Уникальных DX', 'Стран (префиксов)', 'Среднее в день'],
        'Текущий год': [cur_total, df_current['dx'].nunique(), df_current['dx_pfx'].nunique(),
                        round(cur_total / max((df_current['date'].max() - df_current['date'].min()).days, 1), 1)],
        'Прошлый год': [prev_total, df_previous['dx'].nunique(), df_previous['dx_pfx'].nunique(),
                        round(prev_total / max((df_previous['date'].max() - df_previous['date'].min()).days, 1), 1)]
    })
    tags.append(('Сводка сравнения', None, summary.to_html(index=False)))
    return tags

def generate_html_report(all_tags, title="RBN Analyzer Report"):
    today = datetime.date.today().strftime("%Y-%m-%d")
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; color: #333; }}
h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
h2 {{ color: #2980b9; margin-top: 30px; }}
.section {{ background: white; margin: 15px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
img {{ max-width: 100%; border-radius: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: right; }}
th {{ background: #3498db; color: white; }}
tr:nth-child(even) {{ background: #f2f2f2; }}
.footer {{ text-align: center; color: #999; margin-top: 40px; font-size: 0.85em; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>Сгенерировано: {today}</p>
"""
    for section_title, img_path, table_html in all_tags:
        html += f'<div class="section">\n<h2>{section_title}</h2>\n'
        if img_path:
            html += f'<img src="{img_path}" alt="{section_title}">\n'
        html += table_html + '\n</div>\n'
    html += f'<div class="footer">RBN Analyzer &mdash; {today}</div>\n</body>\n</html>'
    report_path = os.path.join(OUTPUT_DIR, "report.html")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML-отчёт: {report_path}")

def main():
    setup_environment()

    print("=" * 60)
    print("RBN ANALYZER — Multi-Band / Multi-Callsign / Comparison")
    print("=" * 60)

    df = collect_data()
    if df is None:
        print("Данные не найдены.")
        return

    print(f"\nВсего спотов: {len(df)}")
    print(f"Позывные: {df['callsign_spotter'].unique().tolist()}")
    print(f"Диапазоны: {df['band'].unique().tolist()}")

    # Сохраняем сырые данные
    df.to_csv(os.path.join(OUTPUT_DIR, "full_data.csv"), index=False)

    all_tags = []

    # --- Текущий год: графики по каждому диапазону ---
    for band in sorted(df['band'].unique()):
        band_df = df[df['band'] == band].copy()
        print(f"\n--- Диапазон {band} ({len(band_df)} спотов) ---")
        tags = generate_charts(band_df)
        all_tags.extend(tags)

    # --- Сравнение с прошлым годом ---
    end_date = datetime.date.today()
    prev_end = end_date - datetime.timedelta(days=DAYS_TO_ANALYZE)
    prev_start = prev_end - datetime.timedelta(days=DAYS_TO_ANALYZE)

    print("\nЗагрузка данных за прошлый год для сравнения...")
    prev_dates = [(prev_start + datetime.timedelta(days=i)).strftime("%Y%m%d")
                  for i in range((prev_end - prev_start).days + 1)]

    prev_frames = []
    for callsign in CALLSIGNS:
        for band in BANDS:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {executor.submit(download_day, d, callsign, band): d for d in prev_dates}
                for future in futures:
                    res = future.result()
                    if res is not None and not res.empty:
                        res = res.copy()
                        res['callsign_spotter'] = callsign
                        prev_frames.append(res)

    if prev_frames:
        df_prev = pd.concat(prev_frames, ignore_index=True)
        df_prev['date'] = pd.to_datetime(df_prev['date'])
        for band in sorted(df['band'].unique()):
            cur_band = df[df['band'] == band].copy()
            prev_band = df_prev[df_prev['band'] == band].copy()
            if not prev_band.empty:
                comp_tags = generate_comparison(cur_band, prev_band)
                all_tags.extend(comp_tags)
    else:
        print("Нет данных за прошлый год для сравнения.")

    # --- HTML-отчёт ---
    generate_html_report(all_tags, title=f"RBN Report — {', '.join(CALLSIGNS)}")
    print("\nГотово!")

if __name__ == "__main__":
    main()
