"""Rhythm-based Dino trainer controlled with timbal hits.

This module expands the original ``DINO_RITMO`` prototype by adding a rhythm
timeline with educational levels inspired by Hindemith exercises and Argentine
folk rhythms. A single timbal (via serial or keyboard fallback) is used to
trigger jumps that must align with the target beat windows.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Sequence

import pygame
import mido

try:
    import serial
except Exception:  # pragma: no cover - optional dependency
    serial = None  # type: ignore[assignment]


def open_serial(port: str | None, baud: int):
    """Open a serial port if pyserial is available and a port was provided."""
    if not port or not serial:
        return None
    try:
        return serial.Serial(port, baudrate=baud, timeout=0)
    except Exception as exc:
        print(f"[warn] Could not open serial port {port}: {exc}")
        return None


def poll_timbal_serial(ser) -> bool:
    """Return True if raw serial data contains a timbal hit marker."""
    if not ser:
        return False
    try:
        waiting = ser.in_waiting
        if not waiting:
            return False
        data = ser.read(waiting)
        if any(marker in data for marker in (b"J", b"H", b"1")):
            return True
        try:
            text = data.decode(errors="ignore").lower()
        except Exception:
            text = ""
        if "hit" in text or "bang" in text or "pad" in text:
            return True
    except Exception:
        return False
    return False


@dataclass(frozen=True)
class RhythmPoint:
    beat: float
    label: str


@dataclass(frozen=True)
class RhythmLevel:
    slug: str
    name: str
    description: str
    tempo: int
    window_ms: int
    base_speed: float
    pattern_length_beats: float
    hit_points: Sequence[RhythmPoint]
    count_in_beats: float = 2.0
    lead_out_beats: float = 2.0
    tags: tuple[str, ...] = ()


@dataclass
class RhythmEvent:
    beat: float
    expected_time: float
    label: str
    window_ms: int
    spawn_time: float = 0.0
    resolved: bool = False
    missed: bool = False
    hit_time: float | None = None
    accuracy_ms: float | None = None

    @property
    def window_seconds(self) -> float:
        return self.window_ms / 1000.0


class RhythmTimeline:
    def __init__(self, level: RhythmLevel) -> None:
        self.level = level
        self.events: list[RhythmEvent] = []
        for point in level.hit_points:
            time_seconds = (
                (level.count_in_beats + point.beat) * 60.0 / level.tempo
            )
            self.events.append(
                RhythmEvent(
                    beat=point.beat,
                    expected_time=time_seconds,
                    label=point.label,
                    window_ms=level.window_ms,
                )
            )
        self.index = 0
        total_beats = (
            level.count_in_beats + level.pattern_length_beats + level.lead_out_beats
        )
        self.total_duration = total_beats * 60.0 / level.tempo

    def reset(self) -> None:
        self.index = 0
        for event in self.events:
            event.resolved = False
            event.missed = False
            event.hit_time = None
            event.accuracy_ms = None

    def assign_spawn_times(self, distance: float, speed: float) -> None:
        travel_time = distance / speed
        for event in self.events:
            event.spawn_time = max(0.0, event.expected_time - travel_time)

    def register_hit(self, now: float) -> tuple[RhythmEvent, float] | None:
        """Try to align a hit with the current event."""
        if self.index >= len(self.events):
            return None
        event = self.events[self.index]
        delta = now - event.expected_time
        if abs(delta) <= event.window_seconds:
            event.resolved = True
            event.hit_time = now
            event.accuracy_ms = abs(delta) * 1000.0
            self.index += 1
            return event, delta
        return None

    def next_timeout(self, now: float) -> RhythmEvent | None:
        """Mark events as missed if their window elapsed."""
        while self.index < len(self.events):
            event = self.events[self.index]
            if now - event.expected_time > event.window_seconds:
                event.missed = True
                self.index += 1
                return event
            break
        return None

    def completion_ratio(self) -> float:
        if not self.events:
            return 1.0
        resolved = sum(1 for ev in self.events if ev.resolved)
        return resolved / len(self.events)

    def is_complete(self) -> bool:
        return all(ev.resolved for ev in self.events)


class TimbalInput:
    """Aggregate hits from serial, MIDI, and optional keyboard fallback."""

    def __init__(self, port: str | None, baud: int) -> None:
        self.ser = open_serial(port, baud)
        self.pending_hits = 0
        self.midi_port = None
        self.keyboard_keys = {
            pygame.K_SPACE,
            pygame.K_UP,
            pygame.K_w,
        }
        try:
            available_ports = mido.get_input_names()
            if not available_ports:
                print("INFO: No se encontraron puertos MIDI de entrada.")
            else:
                self.midi_port = mido.open_input(callback=self.on_midi_message)
                print(f"INFO: Escuchando en puerto MIDI: {self.midi_port.name}")
        except BaseException as e:
            print(f"WARN: No se pudo inicializar el subsistema MIDI: {e}")
            self.midi_port = None

    def on_midi_message(self, message):
        print(f"[DEBUG MIDI] Mensaje recibido: {message}")
        if message.type == 'note_on':
            self.pending_hits += 1

    def handle_pygame_event(self, event) -> None:
        if event.type == pygame.KEYDOWN and event.key in self.keyboard_keys:
            self.pending_hits += 1

    def consume_hit(self) -> bool:
        if self.ser and poll_timbal_serial(self.ser):
            return True
        if self.pending_hits > 0:
            self.pending_hits -= 1
            return True
        return False

    def close(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        if self.midi_port:
            try:
                self.midi_port.close()
            except Exception:
                pass


class Player:
    def __init__(self, x: float, ground_y: float) -> None:
        self.width = 40
        self.height = 40
        self.x = x
        self.ground_y = ground_y
        self.y = ground_y - self.height
        self.vy = 0.0
        self.gravity = 0.78
        self.jump_impulse = -14.0
        self.on_ground = True
        self.color = (25, 25, 25)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, int(self.y), self.width, self.height)

    def update(self) -> None:
        self.y += self.vy
        self.vy += self.gravity
        if self.y >= self.ground_y - self.height:
            self.y = self.ground_y - self.height
            self.vy = 0.0
            self.on_ground = True

    def jump(self) -> None:
        if self.on_ground:
            self.vy = self.jump_impulse
            self.on_ground = False

    def draw(self, surface) -> None:
        pygame.draw.rect(surface, self.color, self.rect, border_radius=6)


class RhythmObstacle:
    def __init__(self, x: float, ground_y: float, event: RhythmEvent) -> None:
        self.width = 34
        self.height = 52
        self.x = x
        self.ground_y = ground_y
        self.y = ground_y - self.height
        self.event = event
        self.base_color = (30, 120, 180)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def update(self, dt: float, speed: float) -> None:
        self.x -= speed * dt

    def draw(self, surface) -> None:
        color = self.base_color
        if self.event.missed:
            color = (200, 60, 60)
        elif self.event.resolved:
            color = (60, 170, 90)
        pygame.draw.rect(surface, color, self.rect, border_radius=6)


class RhythmDinoGame:
    def __init__(
        self,
        level: RhythmLevel,
        *,
        port: str | None,
        baud: int,
        fullscreen: bool = False,
    ) -> None:
        self.level = level
        self.fullscreen = fullscreen
        pygame.init()
        self.width, self.height = 1024, 360
        flags = pygame.FULLSCREEN if fullscreen else 0
        self.screen = pygame.display.set_mode((self.width, self.height), flags)
        pygame.display.set_caption(f"Timbal Dino - {level.name}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas,arial", 22)
        self.small_font = pygame.font.SysFont("consolas,arial", 16)
        self.ground_y = int(self.height * 0.78)
        self.player = Player(80, self.ground_y)
        self.timbal_input = TimbalInput(port, baud)
        self.timeline = RhythmTimeline(level)
        travel_distance = (self.width + 80) - self.player.x
        self.timeline.assign_spawn_times(travel_distance, level.base_speed)
        self.spawn_x = self.width + 80
        self.reset_run()

    def reset_run(self) -> None:
        self.timeline.reset()
        self.obstacles: list[RhythmObstacle] = []
        self.next_spawn_index = 0
        self.state = "running"
        self.fail_reason = ""
        self.score = 0
        self.combo = 0
        self.last_feedback: tuple[str, float] | None = None
        self.run_start = time.perf_counter()

    def close(self) -> None:
        self.timbal_input.close()
        pygame.quit()

    def _score_for_delta(self, delta: float) -> int:
        accuracy = abs(delta) * 1000.0
        window = float(self.level.window_ms)
        quality = max(0.0, 1.0 - (accuracy / window))
        base = 120
        bonus = int(base * (0.25 + 0.75 * quality))
        streak = int(self.combo * 4)
        return bonus + streak

    def _feedback_label(self, event: RhythmEvent, delta: float) -> str:
        direction = "adelantado" if delta < 0 else "tarde"
        accuracy = abs(delta) * 1000.0
        if accuracy <= 25:
            grade = "Perfecto"
        elif accuracy <= 60:
            grade = "Muy bien"
        else:
            grade = "Ajusta"
        return f"{grade}: {event.label} ({accuracy:.0f} ms {direction})"

    def _spawn_event_obstacles(self, now: float) -> None:
        while (
            self.next_spawn_index < len(self.timeline.events)
            and now >= self.timeline.events[self.next_spawn_index].spawn_time
        ):
            event = self.timeline.events[self.next_spawn_index]
            self.obstacles.append(
                RhythmObstacle(self.spawn_x, self.ground_y, event)
            )
            self.next_spawn_index += 1

    def _process_hits(self, now: float) -> None:
        consumed = True
        while consumed and self.state == "running":
            consumed = self.timbal_input.consume_hit()
            if not consumed:
                break
            result = self.timeline.register_hit(now)
            if result:
                event, delta = result
                self.player.jump()
                self.combo += 1
                gained = self._score_for_delta(delta)
                self.score += gained
                self.last_feedback = (self._feedback_label(event, delta), now)
            else:
                self.combo = 0
                self.last_feedback = ("Fuera de ventana", now)

    def _detect_miss(self, now: float) -> None:
        missed = self.timeline.next_timeout(now)
        if missed:
            self.combo = 0
            self.state = "failed"
            self.fail_reason = f"Sin golpe en {missed.label}"

    def _update_world(self, dt: float, now: float) -> None:
        if self.state != "running":
            return
        self._spawn_event_obstacles(now)
        self._process_hits(now)
        self._detect_miss(now)
        if self.state != "running":
            return

        self.player.update()
        for obstacle in self.obstacles:
            obstacle.update(dt, self.level.base_speed)

        self.obstacles = [
            ob for ob in self.obstacles if ob.x + ob.width > -60
        ]

        for obstacle in self.obstacles:
            if obstacle.event.resolved:
                continue
            if self.player.rect.colliderect(obstacle.rect):
                self.state = "failed"
                self.combo = 0
                self.fail_reason = "Impacto con obstaculo"
                break

        if (
            self.state == "running"
            and self.timeline.is_complete()
            and not self.obstacles
        ):
            self.state = "completed"
            self.level_end_time = now

    def _draw_ground(self) -> None:
        pygame.draw.line(
            self.screen,
            (90, 90, 90),
            (0, self.ground_y),
            (self.width, self.ground_y),
            2,
        )

    def _draw_timeline(self, now: float) -> None:
        # Grilla ritmica movil en el suelo
        ground_line_y = self.ground_y + 6

        # Calculamos el pulso actual y el desplazamiento
        seconds_per_beat = 60.0 / self.level.tempo
        # El tiempo "real" del patron comienza despues del count-in
        pattern_time = now - (self.level.count_in_beats * seconds_per_beat)

        # Pixels por segundo ya esta en self.level.base_speed
        # Pixels por pulso = (px/sec) * (sec/pulso)
        pixels_per_beat = self.level.base_speed * seconds_per_beat

        # Cuantos pulsos han pasado visualmente desde el inicio del juego
        # El jugador está en self.player.x, esa es la linea de "hit"
        # El obstaculo aparece en self.spawn_x y viaja hacia el jugador
        travel_time_to_player = (self.spawn_x - self.player.x) / self.level.base_speed

        # El pulso cero (inicio del patron) debe llegar al jugador en t=travel_time_to_player
        # En un tiempo `now`, ¿dónde está el pulso cero?
        # Su tiempo esperado de llegada es `travel_time_to_player`.
        # El tiempo actual es `pattern_time + travel_time_to_player`.
        # El desplazamiento es la diferencia de tiempo, convertida a pixeles.
        time_since_spawn = now - self.timeline.events[0].spawn_time

        # Mejor usemos una referencia móvil: el desplazamiento del mundo
        world_offset = (pattern_time * self.level.base_speed) % pixels_per_beat

        # Dibujamos la grilla
        num_beats_visible = int(self.width / pixels_per_beat) + 2

        for i in range(-1, num_beats_visible):
            # Posicion X del pulso i, relativo al jugador
            beat_x = self.player.x + (i * pixels_per_beat) - world_offset

            # Dibujar subdivisiones (corcheas)
            subdiv_x = beat_x + pixels_per_beat / 2
            if subdiv_x < self.width + 20:
                 pygame.draw.line(self.screen, (200, 200, 200), (subdiv_x, ground_line_y - 8), (subdiv_x, ground_line_y), 1)

            if beat_x < self.width + 20:
                pygame.draw.line(self.screen, (150, 150, 150), (beat_x, ground_line_y - 15), (beat_x, ground_line_y), 2)

        # Linea de HIT o "ahora"
        hit_line_x = self.player.x + self.player.width / 2
        pygame.draw.line(self.screen, (255, 100, 100, 180), (hit_line_x, self.ground_y - 80), (hit_line_x, self.ground_y), 2)

    def _draw_hud(self, now: float) -> None:
        score_text = self.font.render(f"Puntaje: {self.score:05d}", True, (30, 30, 30))
        level_text = self.font.render(
            f"Nivel {self.level.name} ({self.level.tempo} bpm)", True, (30, 30, 30)
        )
        combo_text = self.small_font.render(f"Combo x{self.combo}", True, (60, 60, 60))
        desc_text = self.small_font.render(self.level.description, True, (70, 70, 70))

        self.screen.blit(score_text, (80, 70))
        self.screen.blit(level_text, (80, 100))
        self.screen.blit(combo_text, (80, 130))
        self.screen.blit(desc_text, (80, 156))

        if self.level.tags:
            tags = ", ".join(self.level.tags)
            tags_text = self.small_font.render(f"Referencias: {tags}", True, (100, 100, 100))
            self.screen.blit(tags_text, (80, 180))

        if self.last_feedback and now - self.last_feedback[1] <= 1.8:
            fb_text = self.small_font.render(self.last_feedback[0], True, (20, 20, 150))
            self.screen.blit(fb_text, (80, 210))

        if self.timbal_input.ser:
            port_state = f"Serial {self.timbal_input.ser.port}"
        else:
            port_state = "Teclado activo (Space/Up/W)"
        port_text = self.small_font.render(port_state, True, (90, 90, 90))
        self.screen.blit(port_text, (80, self.height - 36))

    def _draw_state_overlay(self) -> None:
        if self.state == "running":
            return
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((20, 20, 20, 150))
        self.screen.blit(overlay, (0, 0))
        if self.state == "failed":
            lines = [
                "Fallo de compas",
                self.fail_reason,
                "Pulsa Space o Enter para reintentar",
            ]
        else:
            lines = [
                "Nivel completado",
                "Pulsa Space para repetir o ESC para salir",
            ]
        for idx, text in enumerate(lines):
            surface = self.font.render(text, True, (235, 235, 235))
            self.screen.blit(
                surface,
                (
                    self.width // 2 - surface.get_width() // 2,
                    self.height // 2 - 40 + idx * 32,
                ),
            )

    def render(self, now: float) -> None:
        self.screen.fill((245, 245, 245))
        self._draw_ground()
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)
        self.player.draw(self.screen)
        self._draw_timeline(now)
        self._draw_hud(now)
        self._draw_state_overlay()
        pygame.display.flip()

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            now = time.perf_counter() - self.run_start
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
                elif (
                    event.type == pygame.KEYDOWN
                    and event.key in (pygame.K_RETURN, pygame.K_SPACE)
                    and self.state != "running"
                ):
                    self.reset_run()
                    now = time.perf_counter() - self.run_start
                self.timbal_input.handle_pygame_event(event)

            if not running:
                break

            self._update_world(dt, now)
            self.render(now)


def make_level(slug: str, name: str, description: str, tempo: int, window_ms: int, base_speed: float, pattern_length_beats: float, hit_points: Iterable[tuple[float, str]], *, tags: Sequence[str] = (), count_in_beats: float = 2.0, lead_out_beats: float = 2.0) -> RhythmLevel:
    points = tuple(RhythmPoint(beat=beat, label=label) for beat, label in hit_points)
    return RhythmLevel(
        slug=slug,
        name=name,
        description=description,
        tempo=tempo,
        window_ms=window_ms,
        base_speed=base_speed,
        pattern_length_beats=pattern_length_beats,
        hit_points=points,
        count_in_beats=count_in_beats,
        lead_out_beats=lead_out_beats,
        tags=tuple(tags),
    )


def _generate_levels() -> list[RhythmLevel]:
    levels: list[RhythmLevel] = []

    level1_hits = []
    for bar in range(4):
        base = bar * 4.0
        level1_hits.append((base + 0.0, f"{bar + 1}: tiempo 1"))
        level1_hits.append((base + 2.0, f"{bar + 1}: tiempo 3"))
    levels.append(
        make_level(
            slug="pulso_basico",
            name="Pulso 4/4 basico",
            description="Golpea los tiempos fuertes 1 y 3 para mantener el pulso.",
            tempo=92,
            window_ms=150,
            base_speed=320.0,
            pattern_length_beats=16.0,
            hit_points=level1_hits,
            tags=("Pulso basico",),
        )
    )

    level2_hits = []
    for bar in range(4):
        base = bar * 4.0
        level2_hits.append((base + 0.0, f"{bar + 1}: 1"))
        level2_hits.append((base + 1.5, f"{bar + 1}: 2 y"))
        level2_hits.append((base + 3.0, f"{bar + 1}: 4"))
    levels.append(
        make_level(
            slug="hindemith_contratiempo",
            name="Hindemith contratiempo",
            description="Ejercicio inspirado en Elementary Training (unidad de sincopas).",
            tempo=104,
            window_ms=130,
            base_speed=340.0,
            pattern_length_beats=16.0,
            hit_points=level2_hits,
            tags=("Hindemith", "Sincopa"),
        )
    )

    level3_hits = []
    for bar in range(4):
        base = bar * 2.5
        level3_hits.append((base + 0.0, f"{bar + 1}: golpe 1"))
        level3_hits.append((base + 1.5, f"{bar + 1}: subdiv 3"))
    levels.append(
        make_level(
            slug="hindemith_5_8",
            name="Hindemith 5/8 (3+2)",
            description="Agrupa 5/8 como 3+2 siguiendo los acentos secos de timbal.",
            tempo=116,
            window_ms=130,
            base_speed=360.0,
            pattern_length_beats=10.0,
            hit_points=level3_hits,
            tags=("Hindemith", "Compas irregular"),
        )
    )

    zamba_hits = []
    for bar in range(4):
        base = bar * 3.0
        zamba_hits.append((base + 0.0, f"{bar + 1}: apoyo 1"))
        zamba_hits.append((base + 1.5, f"{bar + 1}: vaiven 4"))
        zamba_hits.append((base + 2.5, f"{bar + 1}: floreo 6"))
    levels.append(
        make_level(
            slug="zamba_6_8",
            name="Zamba 6/8",
            description="Replica el pulso bombo-leguero acentuando 1, 4 y 6.",
            tempo=128,
            window_ms=140,
            base_speed=370.0,
            pattern_length_beats=12.0,
            hit_points=zamba_hits,
            tags=("Zamba", "Folklore argentino"),
        )
    )

    chacarera_hits = []
    for bar in range(2):
        base = bar * 6.0
        chacarera_hits.append((base + 0.0, f"{bar + 1}: 1 fuerte"))
        chacarera_hits.append((base + 1.5, f"{bar + 1}: contratiempo 4"))
        chacarera_hits.append((base + 3.0, f"{bar + 1}: acento 7"))
        chacarera_hits.append((base + 4.0, f"{bar + 1}: repique 9"))
        chacarera_hits.append((base + 5.0, f"{bar + 1}: cierre 11"))
    levels.append(
        make_level(
            slug="chacarera_12_8",
            name="Chacarera 12/8",
            description="Trabaja el pattern tradicional de bombo leguero en 12/8.",
            tempo=132,
            window_ms=150,
            base_speed=380.0,
            pattern_length_beats=12.0,
            hit_points=chacarera_hits,
            tags=("Chacarera", "Folklore argentino"),
        )
    )

    return levels


LEVELS = _generate_levels()
LEVEL_BY_SLUG = {lvl.slug: lvl for lvl in LEVELS}


def list_levels() -> None:
    for idx, level in enumerate(LEVELS, start=1):
        timing = f"{level.tempo} bpm"
        tags = ", ".join(level.tags) if level.tags else "sin etiquetas"
        print(
            f"{idx}. {level.name} [{level.slug}] - {timing} - golpes: {len(level.hit_points)} - {tags}"
        )


def pick_level(selector: str | None) -> RhythmLevel:
    if selector is None:
        return LEVELS[0]
    key = selector.lower()
    if key in LEVEL_BY_SLUG:
        return LEVEL_BY_SLUG[key]
    if key.isdigit():
        idx = int(key) - 1
        if 0 <= idx < len(LEVELS):
            return LEVELS[idx]
    for level in LEVELS:
        if level.name.lower() == key:
            return level
    raise ValueError(f"Nivel no encontrado: {selector}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Juego Dino con ritmo guiado para entrenar timbal."
    )
    parser.add_argument(
        "--level",
        help="Slug, nombre o indice del nivel (usa --list-levels para ver opciones).",
    )
    parser.add_argument(
        "--port",
        help="Puerto serial a escuchar para golpes (p.ej. COM4 o /dev/ttyACM0).",
        default=None,
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Baudios del puerto serial.",
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Ejecutar en pantalla completa.",
    )
    parser.add_argument(
        "--list-levels",
        action="store_true",
        help="Listar niveles disponibles y salir.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_levels:
        list_levels()
        return

    try:
        level = pick_level(args.level)
    except ValueError as exc:
        print(exc)
        list_levels()
        sys.exit(1)

    game = RhythmDinoGame(
        level,
        port=args.port,
        baud=args.baud,
        fullscreen=args.fullscreen,
    )
    try:
        game.run()
    finally:
        game.close()


if __name__ == "__main__":
    main()
