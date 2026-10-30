import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.request

import pygame


# -------------------- Configuration --------------------

WIDTH, HEIGHT = 1920, 1080
FPS = 60

# Ollama must be running locally. You can override the model with:
#   OLLAMA_MODEL=llama3.2 python main.py
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

BACKGROUND = (13, 12, 19)
PANEL = (29, 25, 36)
TEXT = (235, 229, 238)
MUTED = (155, 145, 164)
ACCENT = (180, 70, 83)
INPUT_BG = (43, 36, 49)

MOOD_IMAGES = {
    "happy": "happy.png",
    "sad": "sad.png",
    "angry": "angry.png",
    "neutral": "neutral.png",
}
VALID_MOODS = set(MOOD_IMAGES)


# -------------------- LLM connection --------------------

def load_system_prompt():
    """Load the monster's instructions from prompt.txt."""
    try:
        return open("prompt.txt", "r", encoding="utf-8").read().strip()
    except FileNotFoundError:
        print("Error: prompt.txt was not found. Put it beside main.py.")
        sys.exit(1)


def ask_ollama(messages):
    """Send the conversation to Ollama and return the assistant's reply."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result["message"]["content"].strip()

    except urllib.error.URLError as error:
        raise RuntimeError(
            "Couldn't connect to Ollama. Make sure Ollama is running "
            f"and that the model '{MODEL}' is installed.\n\nDetails: {error}"
        )
    except (KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Ollama returned an unexpected response: {error}")


# -------------------- Pygame helpers --------------------

def load_image(filename):
    """Load an image if it exists; return None if it doesn't."""
    try:
        image = pygame.image.load(filename).convert_alpha()
        return image
    except (pygame.error, FileNotFoundError):
        print(f"Warning: couldn't load {filename}")
        return None


def wrap_text(text, font, max_width):
    """Wrap text into lines that fit inside max_width pixels."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        candidate = word if not current_line else current_line + " " + word
        if font.size(candidate)[0] <= max_width:
            current_line = candidate
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines or [""]


def draw_wrapped_text(surface, text, font, color, x, y, max_width, line_gap=8):
    """Draw wrapped text and return the y-coordinate after the final line."""
    line_height = font.get_linesize() + line_gap

    for line in wrap_text(text, font, max_width):
        rendered = font.render(line, True, color)
        surface.blit(rendered, (x, y))
        y += line_height

    return y


def extract_mood(reply):
    """
    Read an optional 'EMOTION: mood' marker.
    The marker is removed from the dialogue shown to the player.
    """
    match = re.search(r"EMOTION:\s*(happy|sad|angry|neutral)", reply, re.IGNORECASE)

    if match:
        mood = match.group(1).lower()
        dialogue = (reply[:match.start()] + reply[match.end():]).strip()
        return mood, dialogue

    return None, reply.strip()


# -------------------- Game --------------------

def main():
    pygame.init()
    pygame.display.set_caption("Not Enough")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()

    # Load the font. The original file had a typo in this line.
    try:
        title_font = pygame.font.Font("Shadows Fright.ttf", 66)
        dialogue_font = pygame.font.Font("Shadows Fright.ttf", 34)
        input_font = pygame.font.Font("Shadows Fright.ttf", 30)
        small_font = pygame.font.Font("Shadows Fright.ttf", 22)
    except FileNotFoundError:
        print("Warning: Shadows Fright.ttf not found; using the default font.")
        title_font = pygame.font.Font(None, 66)
        dialogue_font = pygame.font.Font(None, 34)
        input_font = pygame.font.Font(None, 30)
        small_font = pygame.font.Font(None, 22)

    images = {mood: load_image(filename) for mood, filename in MOOD_IMAGES.items()}
    current_mood = "neutral"

    system_prompt = load_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]

    dialogue = []
    user_input = ""
    input_active = True
    waiting_for_llm = True
    game_over = False
    ending_message = ""

    # Ask the monster for its opening line.
    try:
        first_reply = ask_ollama(messages)
        messages.append({"role": "assistant", "content": first_reply})

        current_mood, first_dialogue = extract_mood(first_reply)
        if current_mood is None:
            current_mood = "neutral"

        if first_dialogue == "IMCONVINCED":
            game_over = True
            ending_message = "The monster finally believes it's scary."
        elif first_dialogue == "IMTOOFARGONE":
            game_over = True
            ending_message = "The monster has lost all hope."
        elif first_dialogue:
            dialogue.append(("monster", first_dialogue))

    except RuntimeError as error:
        dialogue.append(("error", str(error)))

    waiting_for_llm = False
    running = True
    scroll_offset = 0

    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEWHEEL:
                scroll_offset = max(0, scroll_offset - event.y * 35)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 4:
                    scroll_offset = max(0, scroll_offset - 35)
                elif event.button == 5:
                    scroll_offset += 35

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_RETURN and not waiting_for_llm and not game_over:
                    player_message = user_input.strip()

                    if player_message:
                        dialogue.append(("player", player_message))
                        messages.append({"role": "user", "content": player_message})
                        user_input = ""
                        waiting_for_llm = True
                        scroll_offset = 0

                        # Keep the game responsive while waiting for the model.
                        screen.fill(BACKGROUND)
                        loading = dialogue_font.render(
                            "The monster is thinking...", True, MUTED
                        )
                        screen.blit(loading, (WIDTH // 2 - loading.get_width() // 2,
                                              HEIGHT // 2))
                        pygame.display.flip()

                        try:
                            reply = ask_ollama(messages)
                            messages.append({"role": "assistant", "content": reply})

                            mood, monster_dialogue = extract_mood(reply)
                            if mood in VALID_MOODS:
                                current_mood = mood

                            if monster_dialogue == "IMCONVINCED":
                                game_over = True
                                ending_message = "The monster finally believes it's scary."
                            elif monster_dialogue == "IMTOOFARGONE":
                                game_over = True
                                ending_message = "The monster has lost all hope."
                            elif monster_dialogue:
                                dialogue.append(("monster", monster_dialogue))

                        except RuntimeError as error:
                            dialogue.append(("error", str(error)))

                        waiting_for_llm = False
                        scroll_offset = 0

                elif event.key == pygame.K_BACKSPACE and not waiting_for_llm and not game_over:
                    user_input = user_input[:-1]

                elif (
                    event.unicode
                    and event.unicode.isprintable()
                    and not waiting_for_llm
                    and not game_over
                ):
                    user_input += event.unicode

        # -------------------- Draw the interface --------------------

        screen.fill(BACKGROUND)

        # Header
        title = title_font.render("NOT ENOUGH", True, TEXT)
        screen.blit(title, (70, 35))

        subtitle = small_font.render(
            "A conversation with something that wants to be frightening",
            True,
            MUTED,
        )
        screen.blit(subtitle, (75, 112))

        # Monster portrait
        portrait_rect = pygame.Rect(70, 190, 470, 600)
        pygame.draw.rect(screen, PANEL, portrait_rect, border_radius=18)

        portrait = images.get(current_mood)
        if portrait:
           portrait_copy = portrait.copy()

           # Resize while preserving the original aspect ratio
           scale = min(
           420 / portrait_copy.get_width(),
               530 / portrait_copy.get_height()
           )

           new_size = (
              int(portrait_copy.get_width() * scale),
              int(portrait_copy.get_height() * scale)
           )

           portrait_copy = pygame.transform.smoothscale(portrait_copy, new_size)

           portrait_x = portrait_rect.centerx - portrait_copy.get_width() // 2
           portrait_y = portrait_rect.centery - portrait_copy.get_height() // 2

           screen.blit(portrait_copy, (portrait_x, portrait_y))
        else:
            placeholder = title_font.render("?", True, ACCENT)
            screen.blit(
                placeholder,
                (portrait_rect.centerx - placeholder.get_width() // 2,
                 portrait_rect.centery - placeholder.get_height() // 2),
            )

        mood_label = small_font.render(
            f"Mood: {current_mood}", True, MUTED
        )
        screen.blit(
            mood_label,
            (portrait_rect.centerx - mood_label.get_width() // 2, 815),
        )

        # Conversation panel
        chat_rect = pygame.Rect(590, 190, 1260, 690)
        pygame.draw.rect(screen, PANEL, chat_rect, border_radius=18)

        # Draw dialogue, clipping it to the conversation panel.
        chat_surface = pygame.Surface((chat_rect.width - 60, chat_rect.height - 50))
        chat_surface.fill(PANEL)

        y = 0
        for speaker, message in dialogue:
            if speaker == "monster":
                label, color = "MONSTER", ACCENT
            elif speaker == "player":
                label, color = "YOU", (130, 175, 220)
            else:
                label, color = "SYSTEM", (230, 170, 100)

            label_surface = small_font.render(label, True, color)
            chat_surface.blit(label_surface, (0, y))
            y += 32

            y = draw_wrapped_text(
                chat_surface,
                message,
                dialogue_font,
                TEXT,
                0,
                y,
                chat_surface.get_width(),
            )
            y += 28

        max_scroll = max(0, y - chat_surface.get_height())
        scroll_offset = min(scroll_offset, max_scroll)

        screen.blit(
            chat_surface,
            (chat_rect.x + 30, chat_rect.y + 25),
            pygame.Rect(0, scroll_offset, chat_surface.get_width(),
                        chat_surface.get_height()),
        )

        # Input area
        input_rect = pygame.Rect(590, 910, 1260, 95)
        pygame.draw.rect(screen, INPUT_BG, input_rect, border_radius=14)

        if game_over:
            prompt = "THE END — Press ESC to exit"
            input_color = MUTED
        elif waiting_for_llm:
            prompt = "The monster is thinking..."
            input_color = MUTED
        else:
            prompt = user_input + ("|" if pygame.time.get_ticks() % 1000 < 500 else "")
            input_color = TEXT

        input_surface = input_font.render(prompt, True, input_color)
        screen.blit(input_surface, (input_rect.x + 25, input_rect.y + 29))

        if game_over:
            ending = small_font.render(ending_message, True, ACCENT)
            screen.blit(ending, (590, 850))
        else:
            hint = small_font.render("ENTER to send    •    ESC to quit", True, MUTED)
            screen.blit(hint, (590, 1015))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
