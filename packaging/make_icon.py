"""Draw the app icon: the pixel pet on a rounded tile. Usage: make_icon.py OUT.png"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

from claude_usage_widget.ui.pet import COLS, MARGIN_ROWS, ROWS, Mood, pixels_for

SIZE = 512
COLORS = {"B": "#d97757", "F": "#1f2024", "A": "#5fb3ff"}


def main(out: Path) -> None:
    app = QGuiApplication([])  # noqa: F841 - Qt needs an application object for painting
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1c1d21"))
    painter.drawRoundedRect(QRectF(0, 0, SIZE, SIZE), 96, 96)

    cell = SIZE * 0.56 / COLS
    left = (SIZE - COLS * cell) / 2
    top = (SIZE - (ROWS + MARGIN_ROWS) * cell) / 2 + cell * MARGIN_ROWS
    for row, col, role in pixels_for(Mood.HAPPY, tick=0, hop=0):
        painter.setBrush(QColor(COLORS[role]))
        painter.drawRect(QRectF(left + col * cell, top + row * cell, cell, cell))
    painter.end()
    image.save(str(out))
    print(f"wrote {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
