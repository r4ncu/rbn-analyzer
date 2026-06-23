# RBN Analyzer

Web application for analyzing **Reverse Beacon Network** data — spot statistics and visualization by bands, countries, callsigns and time.

## Features

- **Band analysis** — 160m, 80m, 60m, 40m, 30m, 20m, 17m, 15m, 12m, 10m
- **Multilingual** — Russian / English interface
- **10 charts**: top-20 countries, top-20 callsigns, activity by hours, days of week, months, seasons, heatmaps (day×hour, month×hour, country×hour, country×day)
- **Full country names** — 1105 prefix mappings (RU/EN)
- **Flexible period** — buttons: month, 3 months, 6 months, year

<img width="3186" height="20550" alt="RBN-Analyzer-06-23-2026_04_30_PM" src="https://github.com/user-attachments/assets/ed722d8a-7100-4148-87f6-75a13a5d68be" />


## Local Installation

### Requirements

- Python 3.9+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/r4ncu/rbn-analyzer.git
cd rbn-analyzer

# Install dependencies
pip install -r requirements.txt

# Run
python3 app.py
```

Open http://localhost:5000 in your browser.

### Alternative — CLI Script

If you don't need the web interface, there's a standalone script for generating charts:

```bash
python3 rbn_analyzer_20m.py
```

Results will be saved to the `rbn_results_20m/` folder.

## Why It Doesn't Work on Render.com

This application is **not designed** for deployment on Render.com's free tier (or similar free hosting platforms) for the following reasons:

1. **Data volume** — a full year of analysis requires downloading ~1.3 GB of RBN archives (365 files at ~3.5 MB each). Free platforms have strict execution time and memory limits.

2. **Memory** — even with optimizations, processing 365 days of data with pandas, matplotlib and seaborn requires more than 512 MB RAM, which is the limit on Render's free tier.

3. **Execution time** — downloading and processing takes several minutes, exceeding typical free platform timeouts.

4. **Instability** — free instances "sleep" after inactivity and restart on request, interrupting long-running analysis processes.

The application requires a **local computer** or a dedicated server.

## Project Structure

```
rbn_analyzer/
├── app.py              # Flask web application
├── analyzer.py         # Core analysis and chart generation
├── prefix_data.py      # Prefix → country mapping (1105 entries)
├── templates/
│   └── index.html      # Interface (multilingual)
├── requirements.txt    # Dependencies
├── rbn_analyzer_20m.py # CLI script
├── post.md             # Announcement post
└── what.md             # CLI script description
```

## Technologies

- Python, Flask, Pandas, Matplotlib, Seaborn
- csv module (for memory-efficient downloading)
- Gunicorn (production)
