# shiteboard
Python 3 soundboard. It's a bit shite. Definitely works though and it's free, so what have you got to lose.

# Requirements
- [Python 3.11](https://www.python.org/downloads/)
- Packages as seen in [requirements](requirements.txt)
- Some variety of virtual audio cable (tested with [VB-CABLE](https://vb-audio.com/Cable/))

# Tested Platforms
- Windows
- Should work in theory on other platforms (untested)

# Installation
- Download and install [Python 3.11](https://www.python.org/downloads/)
- Download and install a virtual audio cable (recommended: [VB-CABLE](https://vb-audio.com/Cable/))
- Clone the repo
```commandline
git clone https://github.com/soup-dog/soundboard
```
- Navigate to project root
- Set up a virtual environment (optional, but seriously you will thank yourself down the line)
```commandline
python3 -m venv /venv
```
- Install requirements
```commandline
pip install -r requirements.txt
```
- Run [main](main.py)
```commandline
python main.py
```
- Enjoy shiteboard :)

# Upcoming features (who am I kidding)
- Quality of life improvements (~~window title~~, scrollable sound thumbnails)
- Volume adjustment
- ~~Executable using PyInstaller~~
