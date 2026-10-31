# Not enough - A Game About Insecurity
Not Enough is a game about trying to convince a monster that it is scary. You win by successfully convincing the monster that it is such.

## How to run the game
Depencies:
- Python (tested on version 3.14.4)
- Pygame (tested on version 2.6.1)
- Ollama (tested on model Gemma3:4b)
run "Python3 main.py" inside the src/ directory

## How to change the game
- If you want to change the initial prompt for the monster itself, the prompt used is in src/prompt.txt.
- If you want to change the model used, start the program with "OLLAMA_MODEL=[MODEL NAME]" to choose your own installed model.
- If you want to change the assets, the monster's assets are in the img_source/ directory. It was originally made with the .xcf file (used in GIMP), but a .psd file is provided.
- If you want to change anything else, the main.py file has a few easily changeable variable at the top of the file (e.g. width/height, fps, etc.)
