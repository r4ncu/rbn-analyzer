# How to Run RBN Analyzer — Simple Guide

## Step 1: Install Python

If you're on macOS — Python is already installed. Check:

Open **Terminal** (find it via Spotlight, type `Terminal`) and type:

```
python3 --version
```

If you see something like `Python 3.11.x` — you're good, go to Step 2.

If it says `command not found` — download Python from https://www.python.org/downloads/ and install it.

## Step 2: Download the Program

In Terminal, type these one by one (press Enter after each):

```
cd ~/Desktop
```

```
git clone https://github.com/r4ncu/rbn-analyzer.git
```

```
cd rbn-analyzer
```

## Step 3: Install Required Libraries

Type:

```
pip3 install -r requirements.txt
```

Wait for it to finish. May take 1-2 minutes.

## Step 4: Run

Type:

```
python3 app.py
```

You'll see something like:

```
 * Running on http://127.0.0.1:5000
```

## Step 5: Open in Browser

Open your browser (Chrome, Safari, Firefox) and go to:

```
http://localhost:5000
```

Done! You can use it now.

## How to Use

1. In the **Callsign** field, enter your callsign (e.g. `R4NCU`)
2. Select a **band** (default is 20m)
3. Choose a **period** (year, 6 months, 3 months, or month)
4. Click **Run Analysis**
5. Wait — first it downloads data (1-3 minutes), then charts appear

## How to Stop

In Terminal, press `Ctrl+C`

## Common Issues

**"pip3: command not found"**
Try using `pip` instead of `pip3`:
```
pip install -r requirements.txt
```

**"Permission denied"**
Add `--user`:
```
pip3 install --user -r requirements.txt
```

**"Port 5000 already in use"**
Something else is running on this port. Close the previous Terminal window with `app.py` running, or restart your computer.
