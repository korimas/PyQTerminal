from PyQt5.QtCore import QTimer, QRect, Qt, QPoint, QThread
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox, QOpenGLWidget, QScrollBar, QScrollArea, QHBoxLayout, \
    QSizePolicy
from PyQt5.QtGui import QPainter, QClipboard, QFont, QBrush, QColor, QPen, QContextMenuEvent, QFontMetrics, QPixmap, \
    QWheelEvent
import sys
import traceback
from qterminal.backend import SSHBackend
from datetime import datetime

keymap = {
    Qt.Key_Backspace: chr(127).encode(),
    Qt.Key_Escape: chr(27).encode(),
    Qt.Key_AsciiTilde: chr(126).encode(),
    Qt.Key_Up: b'\x1b[A',
    Qt.Key_Down: b'\x1b[B',
    Qt.Key_Left: b'\x1b[D',
    Qt.Key_Right: b'\x1b[C',
    Qt.Key_PageUp: "~1".encode(),
    Qt.Key_PageDown: "~2".encode(),
    Qt.Key_Home: "~H".encode(),
    Qt.Key_End: "~F".encode(),
    Qt.Key_Insert: "~3".encode(),
    Qt.Key_Delete: "~4".encode(),
    Qt.Key_F1: "~a".encode(),
    Qt.Key_F2: "~b".encode(),
    Qt.Key_F3: "~c".encode(),
    Qt.Key_F4: "~d".encode(),
    Qt.Key_F5: "~e".encode(),
    Qt.Key_F6: "~f".encode(),
    Qt.Key_F7: "~g".encode(),
    Qt.Key_F8: "~h".encode(),
    Qt.Key_F9: "~i".encode(),
    Qt.Key_F10: "~j".encode(),
    Qt.Key_F11: "~k".encode(),
    Qt.Key_F12: "~l".encode(),
}
align = Qt.AlignTop | Qt.AlignLeft


class QTerminalWidget(QWidget):
    # backend: pty, ssh
    colors = {
        'black': QColor(0x00, 0x00, 0x00),
        'red': QColor(0xaa, 0x00, 0x00),
        'green': QColor(0x00, 0xaa, 0x00),
        'blue': QColor(0x00, 0x00, 0xaa),
        'cyan': QColor(0x00, 0xaa, 0xaa),
        'brown': QColor(0xaa, 0xaa, 0x00),
        'yellow': QColor(0xff, 0xff, 0x44),
        'magenta': QColor(0xaa, 0x00, 0xaa),
        'white': QColor(0xff, 0xff, 0xff)
    }

    def __init__(self, parent=None):
        super(QTerminalWidget, self).__init__(parent)
        self.setCursor(Qt.IBeamCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.startTimer(100)

        self.font_name = "Consolas"  # 必须用等宽字体: Monospace, Consolas
        self.font_p_size = 15
        self.font = self.new_font()

        # 中文和英文的宽度不同，暂不支持中文
        self.fm = QFontMetrics(self.font)
        self._char_height = self.fm.height()
        self._char_width = self.fm.width("W")
        self._columns, self._rows = self._pixel2pos(self.width(), self.height())

        self.cursor_x = 0
        self.cursor_y = 0
        self._selection = None

        # cache
        self.pens = {}
        self.brushes = {}
        self.default_brush = QBrush(self.colors['black'])
        self.default_pen = QPen(self.colors['white'])

        self.backend = SSHBackend(self._columns, self._rows, '10。182。51。82', 'root', 'hillstone')
        self.pixmap = QPixmap(self.width(), self.height())

        # scroll
        self.scroll = None

    def set_scroll(self, scroll):
        self.scroll = scroll
        self.scroll.setMinimum(0)
        # TODO: len优化，不用每次计算
        tmp = len(self.backend.screen.history.top) + len(self.backend.screen.history.bottom) - self._rows
        self.scroll.setMaximum(tmp if tmp > 0 else 0)
        self.scroll.valueChanged.connect(self.scroll_value_change)

    def scroll_value_change(self, value):
        # TODO： not support jump to pagge of screen
        print('value change: %s' % value)

    def new_font(self):
        font = QFont()
        font.setFamily(self.font_name)
        font.setPixelSize(self.font_p_size)
        return font

    def get_pen(self, color_name):
        pen = self.pens.get(color_name)
        if not pen:
            color = self.colors.get(color_name)
            if not color:
                pen = self.default_pen
            else:
                pen = QPen(color)
            self.pens[color_name] = pen
        return pen

    def get_brush(self, color_name):
        brush = self.brushes.get(color_name)
        if not brush:
            color = self.colors.get(color_name)
            if not color:
                brush = self.default_brush
            else:
                brush = QBrush(color)
            self.brushes[color_name] = brush
        return brush

    def _pixel2pos(self, x, y):
        # 像素转坐标
        col = int(x / self._char_width)
        row = int(y / self._char_height)
        return col, row

    def _pos2pixel(self, col, row):
        # 坐标转像素
        x = col * self._char_width
        y = row * self._char_height
        return x, y

    def resizeEvent(self, event):
        # 调整部件大小触发
        try:
            print('resize')
            self._columns, self._rows = self._pixel2pos(self.width(), self.height())
            self.backend.resize(self._columns, self._rows)
            self.pixmap = QPixmap(self.width(), self.height())
            self.paint_full_pixmap()
        except:
            traceback.print_exc()

    def timerEvent(self, event):
        try:
            cursor = self.backend.cursor()
            if not self.backend.screen.dirty and self.cursor_x == cursor.x and self.cursor_y == cursor.y:
                return

            # TODO: dirty线程之间不安全
            # print(self.backend.screen.dirty)
            self.paint_part_pixmap()
            self.update()
        except:
            traceback.print_exc()

    def paint_selection(self, painter):
        pass

    def draw_text(self, text, start_x, start_y, text_width, fg, bg, painter, align):
        rect = QRect(start_x, start_y, text_width, self._char_height)

        if bg and bg != 'default':
            painter.fillRect(rect, self.get_brush(bg))

        painter.setPen(self.get_pen(fg))
        painter.drawText(rect, align, text)

    def paint_full_text(self, painter):
        painter.setFont(self.font)

        for line_num in range(self._rows):
            self.paint_line_text(painter, line_num, clear=True)

    def paint_dirty_text(self, painter):
        painter.setFont(self.font)
        screen = self.backend.screen

        # 重绘旧光标所在行
        screen.dirty.add(self.cursor_y)

        # 遍历时，dirty会变
        for line_num in screen.dirty:
            self.paint_line_text(painter, line_num, clear=True)

        screen.dirty.clear()

    def paint_line_text(self, painter, line_num, clear=False):
        start_x = 0
        start_y = line_num * self._char_height
        screen = self.backend.screen

        if clear:
            clear_rect = QRect(start_x, start_y, self.width(), self._char_height)
            painter.fillRect(clear_rect, self.default_brush)

        line = screen.buffer[line_num]

        same_text = ""
        text_width = 0
        pre_char = None

        for col in range(screen.columns):
            char = line[col]
            if pre_char and char.fg == pre_char.fg and char.bg == pre_char.bg:
                same_text += char.data
                continue
            else:
                if same_text:
                    text_width = self.fm.width(same_text)
                    self.draw_text(same_text, start_x, start_y, text_width, pre_char.fg, pre_char.bg, painter, align)

                pre_char = char
                same_text = char.data
                start_x = start_x + text_width

        if same_text:
            text_width = self.fm.width(same_text)
            self.draw_text(same_text, start_x, start_y, text_width, pre_char.fg, pre_char.bg, painter, align)

    def pain_cursor(self, painter):
        cursor = self.backend.cursor()
        self.cursor_x = cursor.x
        self.cursor_y = cursor.y
        # pcol = QColor(0x00, 0xaa, 0x00)
        # pen = QPen(pcol)
        bcol = QColor(0x00, 0xaa, 0x00, 80)
        brush = QBrush(bcol)

        painter.setPen(Qt.NoPen)
        painter.setBrush(brush)
        painter.drawRect(QRect(self.cursor_x * self._char_width, self.cursor_y * self._char_height, self._char_width,
                               self._char_height))

    def paint_full_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_full_text(painter)
        self.pain_cursor(painter)

    def paint_part_pixmap(self):
        painter = QPainter(self.pixmap)
        self.paint_dirty_text(painter)
        self.pain_cursor(painter)

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            print(datetime.now())
            painter.drawPixmap(0, 0, self.pixmap)
            print(datetime.now())
            tmp = len(self.backend.screen.history.top) + len(self.backend.screen.history.bottom)
            self.scroll.setMaximum(tmp if tmp > 0 else 0)
            self.scroll.setSliderPosition(len(self.backend.screen.history.top))
        except:
            traceback.print_exc()

    def send(self, data):
        self.backend.write(data)

    def keyPressEvent(self, event):
        text = str(event.text())
        key = event.key()

        modifiers = event.modifiers()
        ctrl = modifiers == Qt.ControlModifier
        if ctrl and key == Qt.Key_Plus:
            self.zoom_in()
        elif ctrl and key == Qt.Key_Minus:
            self.zoom_out()
        else:
            if text and key != Qt.Key_Backspace:
                self.send(text.encode("utf-8"))
            else:
                s = keymap.get(key)
                if s:
                    self.send(s)
        event.accept()

    def closeEvent(self, event):
        self.backend.close()

    def wheelEvent(self, event: QWheelEvent):
        # TODO: 滚轮也会触发滚动条的valueChanged，导致重复设置screen页
        try:
            y = event.angleDelta().y()
            if y > 0:
                self.backend.screen.prev_page()
            else:
                self.backend.screen.next_page()
            self.update()
        except:
            traceback.print_exc()


class QTerminal(QWidget):

    def __init__(self):
        super(QTerminal, self).__init__()
        self.resize(800, 600)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.term = QTerminalWidget(self)
        self.term.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.term)

        self.scroll_bar = QScrollBar(Qt.Vertical, self.term)
        self.layout.addWidget(self.scroll_bar)

        self.term.set_scroll(self.scroll_bar)

    def closeEvent(self, event):
        self.term.close()


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = QTerminal()
        win.show()
        sys.exit(app.exec_())
    except:
        traceback.print_exc()
