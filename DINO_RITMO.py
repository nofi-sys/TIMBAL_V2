# dino_jump.py
import argparse
import random
import sys

import pygame

# pyserial es opcional si usás un Arduino Leonardo/Micro que emule teclado
try:
    import serial
except Exception:
    serial = None


def open_serial(port: str | None, baud: int) -> "serial.Serial | None":
    if not port or not serial:
        return None
    try:
        return serial.Serial(port, baudrate=baud, timeout=0)
    except Exception as e:
        print(f"[Aviso] No pude abrir {port}: {e}")
        return None


def poll_arduino(ser) -> bool:
    """Devuelve True si llegó un 'J' por serial (evento de salto)."""
    if not ser:
        return False
    try:
        n = ser.in_waiting
        if n:
            data = ser.read(n)
            if b"J" in data:
                # Limpiamos cualquier extra para evitar saltos dobles inmediatos
                return True
    except Exception:
        pass
    return False


class Player:
    def __init__(self, x, ground_y):
        self.width = 40
        self.height = 40
        self.x = x
        self.ground_y = ground_y
        self.y = ground_y - self.height
        self.vy = 0.0
        self.gravity = 0.75
        self.jump_impulse = -14.0
        self.on_ground = True
        self.color = (30, 30, 30)

    @property
    def rect(self):
        return pygame.Rect(self.x, int(self.y), self.width, self.height)

    def update(self):
        self.y += self.vy
        self.vy += self.gravity

        if self.y >= self.ground_y - self.height:
            self.y = self.ground_y - self.height
            self.vy = 0.0
            self.on_ground = True

    def jump(self):
        if self.on_ground:
            self.vy = self.jump_impulse
            self.on_ground = False

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect, border_radius=6)


class Cactus:
    def __init__(self, x, ground_y, speed):
        self.width = random.choice([18, 22, 26, 30])
        self.height = random.choice([30, 38, 46, 54, 68])
        self.x = x
        self.ground_y = ground_y
        self.y = ground_y - self.height
        self.speed = speed
        self.color = (10, 120, 40)

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def update(self, dt):
        self.x -= self.speed * dt

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect, border_radius=4)


def spawn_interval_ms():
    # Intervalo entre 900 y 1600 ms para que no sea monótono
    return random.randint(900, 1600)


def main():
    parser = argparse.ArgumentParser(description="Dino jump minimal con soporte Arduino.")
    parser.add_argument("--port", help="Puerto serial del Arduino (p.ej. COM4 o /dev/ttyACM0)", default=None)
    parser.add_argument("--baud", help="Baudios (si usás Serial)", type=int, default=115200)
    args = parser.parse_args()

    pygame.init()
    W, H = 900, 300
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Dino clásico: un botón = un salto")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas,arial", 20)

    ground_y = int(H * 0.8)
    player = Player(80, ground_y)

    # Obstáculos y dificultad
    cacti: list[Cactus] = []
    base_speed = 300.0  # px/s
    speed = base_speed
    speed_increment = 0.012  # acelera muy levemente por frame
    max_speed = 600.0

    # Spawner
    SPAWN = pygame.USEREVENT + 1
    pygame.time.set_timer(SPAWN, spawn_interval_ms())

    # Puntuación
    score = 0
    running = True
    game_over = False

    # Serial
    ser = open_serial(args.port, args.baud)
    if ser:
        print(f"[OK] Escuchando Arduino en {args.port} @ {args.baud}")
        # drenamos el buffer inicial
        try:
            if ser.in_waiting:
                ser.read(ser.in_waiting)
        except Exception:
            pass

    while running:
        dt = clock.tick(60) / 1000.0  # segundos por frame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Salto por teclado (también funciona si el Arduino emula teclado con SPACE)
            if event.type == pygame.KEYDOWN:
                if not game_over and event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    player.jump()
                if game_over and event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    # Restart
                    cacti.clear()
                    player = Player(80, ground_y)
                    speed = base_speed
                    score = 0
                    game_over = False
                    pygame.time.set_timer(SPAWN, spawn_interval_ms())
                    # Limpiamos serial para evitar salto inmediato
                    if ser:
                        try:
                            if ser.in_waiting:
                                ser.read(ser.in_waiting)
                        except Exception:
                            pass

            if event.type == SPAWN and not game_over:
                cacti.append(Cactus(W + 10, ground_y, speed))
                pygame.time.set_timer(SPAWN, spawn_interval_ms())

        # Salto por Arduino Serial (byte 'J')
        if not game_over and poll_arduino(ser):
            player.jump()

        if not game_over:
            # Dificultad: acelera suave hasta max
            speed = min(speed + speed_increment * 60.0, max_speed)

            # Update jugador
            player.update()

            # Update obstáculos
            for c in cacti:
                c.speed = speed
                c.update(dt)

            # Remove fuera de pantalla
            cacti = [c for c in cacti if c.x + c.width > -5]

            # Colisión
            hit = any(player.rect.colliderect(c.rect) for c in cacti)
            if hit:
                game_over = True

            # Score: sube con el tiempo y la velocidad
            score += int(10 * dt * (speed / base_speed))

        # Render
        screen.fill((240, 240, 240))

        # Suelo
        pygame.draw.line(screen, (90, 90, 90), (0, ground_y), (W, ground_y), 2)

        # Dibujos
        player.draw(screen)
        for c in cacti:
            c.draw(screen)

        # UI
        s_text = font.render(f"Score: {score:06d}", True, (20, 20, 20))
        screen.blit(s_text, (10, 10))

        hint = "Espacio/Arriba para saltar" if not ser else "Botón o Espacio para saltar"
        h_text = font.render(hint, True, (70, 70, 70))
        screen.blit(h_text, (10, 35))

        if game_over:
            go1 = font.render("💥 Game Over", True, (150, 30, 30))
            go2 = font.render("Presioná el botón o ESPACIO para reiniciar", True, (60, 60, 60))
            screen.blit(go1, (W // 2 - go1.get_width() // 2, H // 2 - 20))
            screen.blit(go2, (W // 2 - go2.get_width() // 2, H // 2 + 10))

        pygame.display.flip()

    if ser:
        try:
            ser.close()
        except Exception:
            pass
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
