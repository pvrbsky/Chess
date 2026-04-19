from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import chess
from ursina import (
    Button,
    Color,
    EditorCamera,
    Entity,
    InputField,
    Text,
    Ursina,
    Vec3,
    WindowPanel,
    application,
    camera,
    color,
    destroy,
    invoke,
)


DB_PATH = Path("data/database.json")
MAX_USERS = 5
BOARD_TILES = 8
SQUARE_SIZE = 1


@dataclass
class UserProfile:
    name: str
    progress: Dict[str, int]


class JsonDatabase:
    """Jednoduchá JSON databáze: uživatelé + obsah (100 puzzle / 20 exhibicí / 100 lekcí)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._create_seed_data())

    def _create_seed_data(self) -> Dict:
        puzzles = [
            {
                "id": i + 1,
                "title": f"Puzzle #{i + 1}",
                "fen": chess.STARTING_FEN,
                "goal": "Najdi nejlepší tah.",
            }
            for i in range(100)
        ]
        lessons = [
            {
                "id": i + 1,
                "title": f"Lekce #{i + 1}",
                "text": f"Obsah lekce {i + 1}: strategické principy a taktické motivy.",
            }
            for i in range(100)
        ]
        exhibitions = [
            {
                "id": i + 1,
                "robot": f"Robot-{i + 1}",
                "difficulty": random.choice(["easy", "normal", "hard"]),
            }
            for i in range(20)
        ]

        return {
            "users": [],
            "content": {
                "puzzles": puzzles,
                "lessons": lessons,
                "exhibitions": exhibitions,
            },
        }

    def _read(self) -> Dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: Dict) -> None:
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_users(self) -> List[UserProfile]:
        data = self._read()
        return [UserProfile(**u) for u in data["users"]]

    def add_user(self, name: str) -> Optional[str]:
        data = self._read()
        if len(data["users"]) >= MAX_USERS:
            return f"Maximálně {MAX_USERS} uživatelů na zařízení."
        if any(u["name"].lower() == name.lower() for u in data["users"]):
            return "Uživatel už existuje."

        data["users"].append(
            {
                "name": name,
                "progress": {"lessons": 0, "puzzles": 0, "exhibitions": 0},
            }
        )
        self._write(data)
        return None

    def update_progress(self, username: str, mode: str, value: int) -> None:
        data = self._read()
        for user in data["users"]:
            if user["name"] == username:
                user["progress"][mode] = max(user["progress"].get(mode, 0), value)
                break
        self._write(data)

    def get_content(self, key: str) -> List[Dict]:
        return self._read()["content"][key]


class Chess3DApp:
    def __init__(self) -> None:
        self.db = JsonDatabase(DB_PATH)
        self.current_user: Optional[str] = None
        self.board = chess.Board()
        self.selected_square: Optional[int] = None
        self.tile_entities: Dict[int, Entity] = {}
        self.piece_entities: Dict[int, Entity] = {}
        self.ui_entities: List[Entity] = []
        self.info_text: Optional[Text] = None
        self.mode = "menu"

        self.app = Ursina(borderless=False)
        self.app.title = "Chess Academy 3D"
        window = application.window
        window.color = color.rgb(18, 22, 35)

        camera.position = (4, 10, -10)
        camera.rotation_x = 35
        camera.rotation_y = 0
        EditorCamera(enabled=False)

    def clear_ui(self) -> None:
        for e in self.ui_entities:
            destroy(e)
        self.ui_entities = []

    def launch(self) -> None:
        self.show_login_screen()
        self.app.run()

    def show_login_screen(self) -> None:
        self.mode = "login"
        self.clear_ui()

        panel = WindowPanel(title="Vyber uživatele", content=(), enabled=True, scale=(0.7, 0.8))
        panel.position = (0, 0)
        self.ui_entities.append(panel)

        user_names = [u.name for u in self.db.list_users()]
        y = 0.25
        for name in user_names:
            btn = Button(parent=panel, text=name, scale=(0.8, 0.08), y=y)
            btn.on_click = lambda n=name: self._select_user(n)
            self.ui_entities.append(btn)
            y -= 0.1

        self.user_input = InputField(parent=panel, default_value="", y=-0.3, scale=(0.8, 0.08))
        self.ui_entities.append(self.user_input)

        create_btn = Button(parent=panel, text="Vytvořit uživatele", y=-0.4, scale=(0.8, 0.08))
        create_btn.on_click = self._create_user
        self.ui_entities.append(create_btn)

        login_btn = Button(parent=panel, text="Přihlásit se", y=-0.5, scale=(0.8, 0.08), color=color.azure)
        login_btn.on_click = self._login_selected
        self.ui_entities.append(login_btn)

        self.login_msg = Text(parent=panel, text="", y=-0.62, origin=(0, 0), color=color.orange)
        self.ui_entities.append(self.login_msg)

        self.selected_label = Text(parent=panel, text="Vybraný uživatel: žádný", y=-0.22)
        self.ui_entities.append(self.selected_label)

    def _create_user(self) -> None:
        name = self.user_input.text.strip()
        if not name:
            self.login_msg.text = "Zadej jméno uživatele."
            return

        err = self.db.add_user(name)
        if err:
            self.login_msg.text = err
            return

        self.login_msg.text = f"Uživatel {name} vytvořen."
        self.show_login_screen()

    def _select_user(self, name: str) -> None:
        self.current_user = name
        self.selected_label.text = f"Vybraný uživatel: {name}"

    def _login_selected(self) -> None:
        if not self.current_user:
            self.login_msg.text = "Nejprve vyber uživatele."
            return
        self.show_main_menu()

    def show_main_menu(self) -> None:
        self.mode = "menu"
        self.clear_ui()
        self.clear_board()

        title = Text(text=f"Chess Academy 3D — {self.current_user}", y=0.4, scale=1.5)
        self.ui_entities.append(title)

        buttons = [
            ("Hrát partii", self.start_gameplay),
            ("100 lekcí", self.show_lessons),
            ("100 puzzle", self.show_puzzles),
            ("20 exhibicí s roboty", self.show_exhibitions),
            ("Odhlásit", self.show_login_screen),
        ]

        y = 0.2
        for label, handler in buttons:
            b = Button(text=label, scale=(0.5, 0.1), y=y)
            b.on_click = handler
            self.ui_entities.append(b)
            y -= 0.14

    def show_lessons(self) -> None:
        lessons = self.db.get_content("lessons")
        self.show_content_list("Lekce", lessons, "lessons")

    def show_puzzles(self) -> None:
        puzzles = self.db.get_content("puzzles")
        self.show_content_list("Puzzle", puzzles, "puzzles")

    def show_exhibitions(self) -> None:
        ex = self.db.get_content("exhibitions")
        self.show_content_list("Exhibice", ex, "exhibitions")

    def show_content_list(self, title: str, items: List[Dict], mode_key: str) -> None:
        self.mode = mode_key
        self.clear_ui()

        self.ui_entities.append(Text(text=f"{title} ({len(items)})", y=0.42, scale=1.4))
        self.ui_entities.append(Text(text="Klikni na položku pro uložení progresu.", y=0.34, scale=1.0))

        start, stop = 0, 15
        y = 0.22
        for item in items[start:stop]:
            label = item.get("title") or f"{item['robot']} ({item['difficulty']})"
            b = Button(text=label, scale=(0.8, 0.06), y=y)
            b.on_click = lambda id=item["id"]: self._complete_item(mode_key, id)
            self.ui_entities.append(b)
            y -= 0.07

        back = Button(text="Zpět", y=-0.44, scale=(0.3, 0.08), color=color.gray)
        back.on_click = self.show_main_menu
        self.ui_entities.append(back)

        self.progress_msg = Text(text="", y=-0.35)
        self.ui_entities.append(self.progress_msg)

    def _complete_item(self, mode_key: str, item_id: int) -> None:
        self.db.update_progress(self.current_user, mode_key, item_id)
        self.progress_msg.text = f"Uloženo: {mode_key} -> {item_id}"

    def clear_board(self) -> None:
        for ent in self.tile_entities.values():
            destroy(ent)
        for ent in self.piece_entities.values():
            destroy(ent)
        self.tile_entities.clear()
        self.piece_entities.clear()
        if self.info_text:
            destroy(self.info_text)
            self.info_text = None

    def start_gameplay(self) -> None:
        self.mode = "game"
        self.clear_ui()
        self.clear_board()
        self.board.reset()
        self.draw_board()
        self.draw_pieces()

        back = Button(text="Menu", y=0.46, x=-0.78, scale=(0.2, 0.06))
        back.on_click = self.show_main_menu
        self.ui_entities.append(back)

        self.info_text = Text(text="Na tahu: bílý", x=-0.85, y=0.41, scale=1.2)

    def draw_board(self) -> None:
        for rank in range(BOARD_TILES):
            for file in range(BOARD_TILES):
                idx = chess.square(file, rank)
                is_light = (rank + file) % 2 == 0
                tile = Button(
                    model="cube",
                    color=color.rgb(235, 223, 198) if is_light else color.rgb(78, 86, 103),
                    position=Vec3(file * SQUARE_SIZE, 0, rank * SQUARE_SIZE),
                    scale=(0.98, 0.05, 0.98),
                    collider="box",
                    highlight_color=color.yellow,
                )
                tile.on_click = lambda sq=idx: self.on_square_click(sq)
                self.tile_entities[idx] = tile

    def draw_pieces(self) -> None:
        for sq, entity in list(self.piece_entities.items()):
            destroy(entity)
            del self.piece_entities[sq]

        for square, piece in self.board.piece_map().items():
            file = chess.square_file(square)
            rank = chess.square_rank(square)
            col = color.white if piece.color == chess.WHITE else color.black
            glyph = self._piece_model(piece)
            ent = Entity(
                model=glyph,
                color=col,
                position=Vec3(file, 0.25, rank),
                scale=(0.55, 0.55, 0.55),
            )
            self.piece_entities[square] = ent

    def _piece_model(self, piece: chess.Piece) -> str:
        # Jednoduché 3D tvary pro různé figury
        return {
            chess.PAWN: "sphere",
            chess.KNIGHT: "cube",
            chess.BISHOP: "cone",
            chess.ROOK: "cube",
            chess.QUEEN: "cylinder",
            chess.KING: "capsule",
        }[piece.piece_type]

    def on_square_click(self, square: int) -> None:
        if self.mode != "game":
            return

        piece = self.board.piece_at(square)
        turn = self.board.turn

        if self.selected_square is None:
            if piece and piece.color == turn:
                self.selected_square = square
                self.info_text.text = f"Vybráno: {chess.square_name(square)}"
            return

        move = chess.Move(self.selected_square, square)
        if move in self.board.legal_moves:
            self.board.push(move)
            self.draw_pieces()
            self.selected_square = None
            self._post_move_updates()
            return

        self.selected_square = None
        self.info_text.text = "Neplatný tah."

    def _post_move_updates(self) -> None:
        self.info_text.text = "Na tahu: bílý" if self.board.turn == chess.WHITE else "Na tahu: černý"

        if self.board.is_checkmate():
            winner = "Bílý" if self.board.turn == chess.BLACK else "Černý"
            self.info_text.text = f"Šachmat! Vítěz: {winner}"
            self.checkmate_vfx()

    def checkmate_vfx(self) -> None:
        king_square = self.board.king(self.board.turn)
        if king_square is None:
            return

        file = chess.square_file(king_square)
        rank = chess.square_rank(king_square)

        glass_tower = Entity(
            model="cube",
            position=Vec3(file, 0.25, rank),
            scale=(0.4, 0.4, 0.4),
            color=Color(1, 0, 0, 0.5),
        )

        def grow_tower() -> None:
            glass_tower.scale_y += 0.18
            glass_tower.y += 0.09
            if glass_tower.scale_y < 4.5:
                invoke(grow_tower, delay=0.05)
            else:
                explode(glass_tower)

        def explode(tower: Entity) -> None:
            for _ in range(35):
                Entity(
                    model="sphere",
                    color=color.red,
                    position=tower.position,
                    scale=0.08,
                    animate_position=(
                        tower.x + random.uniform(-2, 2),
                        tower.y + random.uniform(0.2, 2),
                        tower.z + random.uniform(-2, 2),
                    ),
                    duration=0.45,
                )
            destroy(tower, delay=0.2)

        grow_tower()


if __name__ == "__main__":
    Chess3DApp().launch()
