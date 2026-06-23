import datetime
import requests
import zipfile
import io
import os
from concurrent.futures import ThreadPoolExecutor
from prefix_data import PREFIX_TO_COUNTRY, PREFIX_TO_COUNTRY_EN

import pandas as pd

RBN_URL = "https://data.reversebeacon.net/rbn_history/{date}.zip"

ALL_BANDS = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m"]
ALL_DAYS_EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
ALL_DAYS_RU = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
ALL_MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December']
ALL_MONTHS_RU = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
SEASON_MAP = {12: 'Зима', 1: 'Зима', 2: 'Зима',
              3: 'Весна', 4: 'Весна', 5: 'Весна',
              6: 'Лето', 7: 'Лето', 8: 'Лето',
              9: 'Осень', 10: 'Осень', 11: 'Осень'}
SEASON_MAP_EN = {12: 'Winter', 1: 'Winter', 2: 'Winter',
                 3: 'Spring', 4: 'Spring', 5: 'Spring',
                 6: 'Summer', 7: 'Summer', 8: 'Summer',
                 9: 'Autumn', 10: 'Autumn', 11: 'Autumn'}
SEASON_ORDER = ['Зима', 'Весна', 'Лето', 'Осень']
SEASON_ORDER_EN = ['Winter', 'Spring', 'Summer', 'Autumn']


def resolve_country(prefix, lang='ru'):
    p = str(prefix).strip().upper()
    if lang == 'en':
        if p in PREFIX_TO_COUNTRY_EN:
            return PREFIX_TO_COUNTRY_EN[p]
        for k, v in sorted(PREFIX_TO_COUNTRY_EN.items(), key=lambda x: -len(x[0])):
            if p.startswith(k):
                return v
        return p
    else:
        if p in PREFIX_TO_COUNTRY:
            return PREFIX_TO_COUNTRY[p]
        for k, v in sorted(PREFIX_TO_COUNTRY.items(), key=lambda x: -len(x[0])):
            if p.startswith(k):
                return v
        return p


def download_day(date_str, callsign, band):
    url = RBN_URL.format(date=date_str)
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                csv_name = f"{date_str}.csv"
                if csv_name in z.namelist():
                    with z.open(csv_name) as f:
                        df = pd.read_csv(f, low_memory=False)
                        filtered = df[(df['callsign'] == callsign) & (df['band'] == band)]
                        return filtered
        else:
            print(f"HTTP {resp.status_code} for {date_str}")
    except Exception as e:
        print(f"Error {date_str}: {e}")
    return None


def collect_data(callsigns, bands, days=365, progress_cb=None):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=days)
    dates = [(start_date + datetime.timedelta(days=i)).strftime("%Y%m%d")
             for i in range(days + 1)]

    frames = []
    total = len(callsigns) * len(bands) * len(dates)
    done = 0
    errors = 0

    for cs in callsigns:
        for band in bands:
            print(f"Starting download: {cs} / {band} / {len(dates)} days")
            with ThreadPoolExecutor(max_workers=5) as ex:
                futures = {ex.submit(download_day, d, cs, band): d for d in dates}
                for fut in futures:
                    res = fut.result()
                    if res is not None and not res.empty:
                        r = res.copy()
                        r['callsign_spotter'] = cs
                        frames.append(r)
                    else:
                        errors += 1
                    done += 1
                    if progress_cb and (done % 20 == 0 or done == total):
                        progress_cb(done, total)
            print(f"Done: {cs}/{band} — {len(frames)} frames, {errors} errors")

    if not frames:
        print(f"No data collected. Total errors: {errors}/{total}")
        return None
    df = pd.concat(frames, ignore_index=True)
    df['date'] = pd.to_datetime(df['date'])
    print(f"Final dataset: {len(df)} rows")
    return df


def make_charts(df, output_dir, lang='ru'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    os.makedirs(output_dir, exist_ok=True)
    results = []
    bands = sorted(df['band'].unique(), key=lambda b: ALL_BANDS.index(b) if b in ALL_BANDS else 999)

    month_names = ALL_MONTHS_RU if lang == 'ru' else ALL_MONTHS_EN
    day_names = ALL_DAYS_RU if lang == 'ru' else ALL_DAYS_EN
    season_map = SEASON_MAP if lang == 'ru' else SEASON_MAP_EN
    season_order = SEASON_ORDER if lang == 'ru' else SEASON_ORDER_EN

    for band in bands:
        bdf = df[df['band'] == band].copy()
        prefix = f"{band}_"

        # Топ-20 стран
        fig, ax = plt.subplots(figsize=(12, 7))
        country_series = bdf['dx_pfx'].apply(lambda p: resolve_country(p, lang)).value_counts().head(20)
        sns.barplot(x=country_series.values, y=country_series.index, hue=country_series.index, palette='viridis', legend=False, ax=ax)
        ax.set_title(f'Top-20 Countries — {band}')
        fname = prefix + 'countries.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'countries', 'file': fname,
                        'title': 'Топ-20 стран — ' + band if lang == 'ru' else f'Top-20 Countries — {band}',
                        'data': [{'country': c, 'count': int(n)} for c, n in country_series.items()]})

        # Топ-20 позывных
        fig, ax = plt.subplots(figsize=(12, 7))
        stats = bdf['dx'].value_counts().head(20)
        sns.barplot(x=stats.values, y=stats.index, hue=stats.index, palette='magma', legend=False, ax=ax)
        ax.set_title(f'Top-20 Callsigns — {band}')
        fname = prefix + 'callsigns.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'callsigns', 'file': fname,
                        'title': 'Топ-20 позывных — ' + band if lang == 'ru' else f'Top-20 Callsigns — {band}',
                        'data': [{'callsign': c, 'count': int(n)} for c, n in stats.items()]})

        # Часы
        bdf['hour'] = bdf['date'].dt.hour
        fig, ax = plt.subplots(figsize=(12, 5))
        hs = bdf['hour'].value_counts().sort_index()
        sns.lineplot(x=hs.index, y=hs.values, marker='o', color='#2980b9', ax=ax, linewidth=2)
        ax.set_title(f'Activity by Hour (UTC) — {band}')
        ax.set_xticks(range(24))
        ax.set_ylabel('Spots')
        fname = prefix + 'hours.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'hours', 'file': fname,
                        'title': 'Активность по часам — ' + band if lang == 'ru' else f'Activity by Hour — {band}',
                        'data': [{'hour': int(h), 'count': int(c)} for h, c in hs.items()]})

        # Дни недели
        bdf['day_name'] = bdf['date'].dt.day_name()
        fig, ax = plt.subplots(figsize=(10, 5))
        day_labels = ALL_DAYS_RU if lang == 'ru' else ALL_DAYS_EN
        day_map = dict(zip(ALL_DAYS_EN, ALL_DAYS_RU))
        bdf['day_label'] = bdf['day_name'].map(day_map) if lang == 'ru' else bdf['day_name']
        order_labels = ALL_DAYS_RU if lang == 'ru' else ALL_DAYS_EN
        sns.countplot(data=bdf, x='day_label', order=order_labels, hue='day_label', palette='YlGnBu', legend=False, ax=ax)
        ax.set_title(f'Activity by Day — {band}' if lang == 'en' else f'Активность по дням — {band}')
        ax.set_xlabel('')
        fname = prefix + 'days.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        dc = bdf['day_label'].value_counts().reindex(order_labels, fill_value=0)
        results.append({'band': band, 'type': 'days', 'file': fname,
                        'title': 'Дни недели — ' + band if lang == 'ru' else f'Days of Week — {band}',
                        'data': [{'day': d, 'count': int(c)} for d, c in dc.items()]})

        # Месяцы
        bdf['month_num'] = bdf['date'].dt.month
        fig, ax = plt.subplots(figsize=(12, 5))
        month_labels = ALL_MONTHS_RU if lang == 'ru' else ALL_MONTHS_EN
        month_map_en_to_ru = dict(zip(ALL_MONTHS_EN, ALL_MONTHS_RU))
        bdf['month_label'] = bdf['date'].dt.month_name().map(month_map_en_to_ru) if lang == 'ru' else bdf['date'].dt.month_name()
        sns.countplot(data=bdf, x='month_label', order=month_labels, hue='month_label', palette='coolwarm', legend=False, ax=ax)
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45)
        ax.set_title(f'Activity by Month — {band}' if lang == 'en' else f'Активность по месяцам — {band}')
        ax.set_xlabel('')
        fname = prefix + 'months.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        mc = bdf['month_label'].value_counts().reindex(month_labels, fill_value=0)
        results.append({'band': band, 'type': 'months', 'file': fname,
                        'title': 'Месяцы — ' + band if lang == 'ru' else f'Months — {band}',
                        'data': [{'month': m, 'count': int(c)} for m, c in mc.items()]})

        # Сезоны
        smap = SEASON_MAP if lang == 'ru' else SEASON_MAP_EN
        sorder = SEASON_ORDER if lang == 'ru' else SEASON_ORDER_EN
        bdf['season'] = bdf['date'].dt.month.map(smap)
        fig, ax = plt.subplots(figsize=(7, 7))
        sc = bdf['season'].value_counts().reindex(sorder, fill_value=0)
        ax.pie(sc[sc > 0], labels=sc[sc > 0].index, autopct='%1.1f%%', colors=sns.color_palette('pastel'))
        ax.set_title(f'Seasons — {band}' if lang == 'en' else f'Сезоны — {band}')
        fname = prefix + 'seasons.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'seasons', 'file': fname,
                        'title': 'Сезоны — ' + band if lang == 'ru' else f'Seasons — {band}',
                        'data': [{'season': s, 'count': int(c)} for s, c in sc.items()]})

        # Heatmap день×час
        bdf['hour'] = bdf['date'].dt.hour
        day_order_en = ALL_DAYS_EN
        day_order_labels = ALL_DAYS_RU if lang == 'ru' else ALL_DAYS_EN
        day_map_full = dict(zip(ALL_DAYS_EN, ALL_DAYS_RU))
        bdf['day_for_heat'] = bdf['day_name'].map(day_map_full) if lang == 'ru' else bdf['day_name']
        piv = bdf.groupby(['day_for_heat', 'hour']).size().unstack(fill_value=0).reindex(day_order_labels, fill_value=0)
        fig, ax = plt.subplots(figsize=(14, 5))
        sns.heatmap(piv, cmap='YlOrRd', ax=ax, cbar_kws={'label': 'Spots'})
        ax.set_title(f'Heatmap: Day × Hour — {band}')
        ax.set_ylabel('')
        fname = prefix + 'heatmap_dh.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'heatmap_dh', 'file': fname,
                        'title': 'Heatmap день×час — ' + band if lang == 'ru' else f'Heatmap Day×Hour — {band}',
                        'data': []})

        # Heatmap месяц×час
        piv = bdf.groupby(['month_label', 'hour']).size().unstack(fill_value=0).reindex(month_labels, fill_value=0)
        fig, ax = plt.subplots(figsize=(14, 5))
        sns.heatmap(piv, cmap='YlGnBu', ax=ax, cbar_kws={'label': 'Spots'})
        ax.set_title(f'Heatmap: Month × Hour — {band}')
        ax.set_ylabel('')
        fname = prefix + 'heatmap_mh.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'heatmap_mh', 'file': fname,
                        'title': 'Heatmap месяц×час — ' + band if lang == 'ru' else f'Heatmap Month×Hour — {band}',
                        'data': []})

        # Heatmap страна×час (топ-10)
        bdf['country'] = bdf['dx_pfx'].apply(lambda p: resolve_country(p, lang))
        top10 = bdf['country'].value_counts().head(10).index.tolist()
        bdf_top10 = bdf[bdf['country'].isin(top10)]
        piv = bdf_top10.groupby(['country', 'hour']).size().unstack(fill_value=0)
        piv = piv.reindex(top10)
        fig, ax = plt.subplots(figsize=(14, 6))
        sns.heatmap(piv, cmap='YlOrRd', ax=ax, cbar_kws={'label': 'Spots'})
        ax.set_title(f'Country × Hour — {band}' if lang == 'en' else f'Страна×час — {band}')
        ax.set_ylabel('')
        fname = prefix + 'heatmap_ch.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'heatmap_ch', 'file': fname,
                        'title': 'Heatmap страна×час — ' + band if lang == 'ru' else f'Heatmap Country×Hour — {band}',
                        'data': []})

        # Heatmap страна×день недели (топ-10)
        day_map_full = dict(zip(ALL_DAYS_EN, ALL_DAYS_RU))
        day_order_labels = ALL_DAYS_RU if lang == 'ru' else ALL_DAYS_EN
        bdf_top10['day_for_heat2'] = bdf_top10['day_name'].map(day_map_full) if lang == 'ru' else bdf_top10['day_name']
        piv2 = bdf_top10.groupby(['country', 'day_for_heat2']).size().unstack(fill_value=0)
        piv2 = piv2.reindex(columns=day_order_labels, index=top10, fill_value=0)
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(piv2, cmap='YlGnBu', ax=ax, cbar_kws={'label': 'Spots'})
        ax.set_title(f'Country × Day — {band}' if lang == 'en' else f'Страна×день — {band}')
        ax.set_ylabel('')
        fname = prefix + 'heatmap_cd.png'
        fig.savefig(os.path.join(output_dir, fname), bbox_inches='tight')
        plt.close(fig)
        results.append({'band': band, 'type': 'heatmap_cd', 'file': fname,
                        'title': 'Heatmap страна×день — ' + band if lang == 'ru' else f'Heatmap Country×Day — {band}',
                        'data': []})

    return results


def make_summary(df, lang='ru'):
    total = len(df)
    days_count = max((df['date'].max() - df['date'].min()).days, 1)
    return {
        'total_spots': total,
        'unique_dx': int(df['dx'].nunique() or 0),
        'unique_countries': int(df['dx_pfx'].apply(lambda p: resolve_country(p, lang)).nunique() or 0),
        'avg_per_day': round(total / days_count, 1),
        'bands': sorted(df['band'].unique().tolist(), key=lambda b: ALL_BANDS.index(b) if b in ALL_BANDS else 999),
        'callsigns': sorted(df['callsign_spotter'].unique().tolist()),
        'date_range': f"{df['date'].min().strftime('%Y-%m-%d')} — {df['date'].max().strftime('%Y-%m-%d')}",
    }
