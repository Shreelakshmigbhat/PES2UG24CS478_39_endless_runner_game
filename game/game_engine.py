from pathlib import Path

import pygame
from .player import Player
from .obstacle import Obstacle

# Game Engine

WHITE = (255, 255, 255)
BROWN = (120, 80, 40)
DARK_GREEN = (30, 100, 30)

class GameEngine:
    DIFFICULTIES = {
        "Easy": (4, 100),
        "Medium": (6, 70),
        "Hard": (8, 55),
    }

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.ground_y = height - 40

        self.max_speed = 12
        self.speed_increase_per_frame = 0.003
        self.font = pygame.font.SysFont("Arial", 30)
        self.game_over_font = pygame.font.SysFont("Arial", 56, bold=True)
        self.final_score_font = pygame.font.SysFont("Arial", 32)
        self.prompt_font = pygame.font.SysFont("Arial", 22)
        self.sounds = self._load_sounds()
        self.reset("Medium")

    def _load_sounds(self):
        """Load optional effects; the game still works if audio is unavailable."""
        sound_dir = Path(__file__).resolve().parent.parent / "assets" / "sounds"
        sound_files = {
            "jump": "jump.wav",
            "score": "score.wav",
            "game_over": "game_over.wav",
        }

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error:
            return {}

        sounds = {}
        for effect, filename in sound_files.items():
            try:
                sounds[effect] = pygame.mixer.Sound(str(sound_dir / filename))
            except (OSError, pygame.error):
                # Missing or unsupported files simply disable that effect.
                continue
        return sounds

    def _play_sound(self, effect):
        sound = self.sounds.get(effect)
        if sound is not None:
            try:
                sound.play()
            except pygame.error:
                # Audio device errors should not interrupt gameplay.
                pass

    def reset(self, difficulty):
        """Start a fresh run using the selected starting speed and spawn rate."""
        self.difficulty = difficulty
        self.speed, self.spawn_interval = self.DIFFICULTIES[difficulty]
        self.player = Player(80, self.ground_y)
        self._spawn_timer = 0
        self.obstacles = []
        self.distance = 0
        self.score = 0
        self.game_over = False
        self.exit_requested = False

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        if self.game_over:
            choices = {
                pygame.K_1: "Easy",
                pygame.K_2: "Medium",
                pygame.K_3: "Hard",
            }
            if event.key in choices:
                self.reset(choices[event.key])
            elif event.key in (pygame.K_4, pygame.K_ESCAPE):
                self.exit_requested = True
            return

        if event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
            if self.player.on_ground:
                self.player.jump()
                self._play_sound("jump")

    def handle_input(self):
        # Reserved for continuously-held-key input; this runner only
        # needs an edge-triggered jump, handled in handle_event.
        pass

    def update(self):
        if self.game_over:
            return

        self.speed = min(self.speed + self.speed_increase_per_frame, self.max_speed)
        previous_player_y = self.player.y
        self.player.update()

        self._spawn_timer += 1
        if self._spawn_timer >= self.spawn_interval:
            self._spawn_timer = 0
            self.obstacles.append(Obstacle(self.width, self.ground_y, self.speed))

        previous_obstacle_x = {}
        for obstacle in self.obstacles:
            previous_obstacle_x[obstacle] = obstacle.x
            obstacle.move()
            obstacle.speed = self.speed

        for obstacle in self.obstacles:
            if self._swept_collision(
                previous_obstacle_x[obstacle], obstacle.x,
                previous_player_y, self.player.y,
                obstacle.width, obstacle.height,
            ):
                self.game_over = True
                self._play_sound("game_over")
                return

        for obstacle in self.obstacles:
            if not obstacle.scored and obstacle.x + obstacle.width < self.player.x:
                obstacle.scored = True
                self.score += 1
                self._play_sound("score")

        self.obstacles = [o for o in self.obstacles if not o.off_screen()]

        self.distance += self.speed

    def _swept_collision(self, old_obstacle_x, new_obstacle_x,
                         old_player_y, new_player_y,
                         obstacle_width, obstacle_height):
        """Check overlap at any point during this frame, not just at its end."""
        # Work in relative coordinates: the obstacle moves horizontally and
        # the player vertically. Expand the obstacle by the player's size,
        # then test the relative motion segment against that rectangle.
        start_x = old_obstacle_x - self.player.x
        start_y = self.ground_y - obstacle_height - old_player_y
        delta_x = (new_obstacle_x - old_obstacle_x)
        delta_y = -(new_player_y - old_player_y)

        x_entry, x_exit = self._axis_overlap_times(
            start_x, delta_x, -obstacle_width, self.player.width
        )
        y_entry, y_exit = self._axis_overlap_times(
            start_y, delta_y, -obstacle_height, self.player.height
        )
        if x_entry is None or y_entry is None:
            return False

        entry_time = max(x_entry, y_entry)
        exit_time = min(x_exit, y_exit)
        return entry_time <= exit_time and exit_time >= 0 and entry_time <= 1

    @staticmethod
    def _axis_overlap_times(position, velocity, minimum, maximum):
        """Return the time interval where a moving point lies in an interval."""
        if velocity == 0:
            if minimum < position < maximum:
                return float("-inf"), float("inf")
            return None, None

        first = (minimum - position) / velocity
        second = (maximum - position) / velocity
        return min(first, second), max(first, second)

    def render(self, screen):
        pygame.draw.line(screen, BROWN, (0, self.ground_y), (self.width, self.ground_y), 4)

        pygame.draw.rect(screen, WHITE, self.player.rect())
        for obstacle in self.obstacles:
            pygame.draw.rect(screen, DARK_GREEN, obstacle.rect())

        score_text = self.font.render(f"Score: {self.score}", True, (0, 0, 0))
        screen.blit(score_text, (10, 10))

        if self.game_over:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            screen.blit(overlay, (0, 0))

            game_over_text = self.game_over_font.render("GAME OVER", True, WHITE)
            final_score_text = self.final_score_font.render(
                f"Final Score: {self.score}", True, WHITE
            )
            prompt_text = self.prompt_font.render(
                "Replay: 1 Easy   2 Medium   3 Hard   |   4 Exit",
                True, WHITE,
            )

            screen.blit(game_over_text, game_over_text.get_rect(
                center=(self.width // 2, self.height // 2 - 55)
            ))
            screen.blit(final_score_text, final_score_text.get_rect(
                center=(self.width // 2, self.height // 2 - 15)
            ))
            screen.blit(prompt_text, prompt_text.get_rect(
                center=(self.width // 2, self.height // 2 + 45)
            ))
