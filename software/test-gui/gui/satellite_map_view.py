
import math
import os

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QWidget

from gui import theme

TILE_SIZE = 256
MIN_ZOOM = 2
MAX_ZOOM = 19
DEFAULT_CENTER_LAT = 0.0
DEFAULT_CENTER_LON = 0.0
DEFAULT_ZOOM = 3

# Esri World Imagery, no key needed. note z/y/x, not z/x/y
TILE_URL_TEMPLATE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ATTRIBUTION_TEXT = "Tiles © Esri, Maxar, Earthstar Geographics"
USER_AGENT = "OrinNAV-Test-GUI/0.1 (local testing)"
CACHE_DIR = os.path.expanduser("~/.cache/orinnav/satellite_tiles")

MARKER_COLOR = QColor("#2a7de1")
MARKER_RADIUS = 6
MARKER_RING_WIDTH = 2
MARKER_HALO_RADIUS = 14


def _lonlat_to_pixel(lon, lat, zoom):
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    y = (
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
        * TILE_SIZE
    )
    return x, y


def _pixel_to_lonlat(x, y, zoom):
    n = 2 ** zoom
    lon = x / (n * TILE_SIZE) * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / (n * TILE_SIZE))))
    return lon, math.degrees(lat_rad)


class SatelliteMapView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setMouseTracking(True)

        self._center_lat = DEFAULT_CENTER_LAT
        self._center_lon = DEFAULT_CENTER_LON
        self._zoom = DEFAULT_ZOOM

        self._dragging = False
        self._last_drag_pos = QPointF()

        self._tile_cache = {}
        self._pending = set()

        self._marker_lat = None
        self._marker_lon = None

        os.makedirs(CACHE_DIR, exist_ok=True)
        self._network = QNetworkAccessManager(self)

    def set_center(self, lat, lon, zoom=None):
        self._center_lat = lat
        self._center_lon = lon
        if zoom is not None:
            self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        self.update()

    def set_marker(self, lat, lon):
        # None for both clears it
        self._marker_lat = lat
        self._marker_lon = lon
        self.update()

    def _disk_cache_path(self, z, x, y):
        return os.path.join(CACHE_DIR, str(z), str(x), f"{y}.png")

    def _get_tile(self, z, x, y):
        n = 2 ** z
        x %= n
        if y < 0 or y >= n:
            return None

        key = (z, x, y)
        cached = self._tile_cache.get(key)
        if cached is not None:
            return cached

        disk_path = self._disk_cache_path(z, x, y)
        if os.path.exists(disk_path):
            pixmap = QPixmap(disk_path)
            if not pixmap.isNull():
                self._tile_cache[key] = pixmap
                return pixmap

        if key not in self._pending:
            self._pending.add(key)
            request = QNetworkRequest(QUrl(TILE_URL_TEMPLATE.format(z=z, x=x, y=y)))
            request.setRawHeader(b"User-Agent", USER_AGENT.encode("ascii"))
            reply = self._network.get(request)
            reply.finished.connect(lambda r=reply, k=key: self._on_tile_loaded(r, k))
        return None

    def _on_tile_loaded(self, reply, key):
        self._pending.discard(key)
        data = reply.readAll()
        reply.deleteLater()
        if reply.error() != reply.NetworkError.NoError or data.isEmpty():
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        self._tile_cache[key] = pixmap

        z, x, y = key
        disk_path = self._disk_cache_path(z, x, y)
        os.makedirs(os.path.dirname(disk_path), exist_ok=True)
        pixmap.save(disk_path, "PNG")

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), theme.MAP_BACKGROUND)

        width, height = self.width(), self.height()
        center_px_x, center_px_y = _lonlat_to_pixel(
            self._center_lon, self._center_lat, self._zoom
        )
        top_left_x = center_px_x - width / 2.0
        top_left_y = center_px_y - height / 2.0

        first_tx = math.floor(top_left_x / TILE_SIZE)
        first_ty = math.floor(top_left_y / TILE_SIZE)
        last_tx = math.floor((top_left_x + width) / TILE_SIZE)
        last_ty = math.floor((top_left_y + height) / TILE_SIZE)

        for tx in range(first_tx, last_tx + 1):
            for ty in range(first_ty, last_ty + 1):
                screen_x = tx * TILE_SIZE - top_left_x
                screen_y = ty * TILE_SIZE - top_left_y
                tile = self._get_tile(self._zoom, tx, ty)
                target = QRectF(screen_x, screen_y, TILE_SIZE, TILE_SIZE)
                if tile is not None:
                    painter.drawPixmap(target, tile, QRectF(tile.rect()))
                else:
                    painter.fillRect(target.adjusted(1, 1, -1, -1), theme.MAP_TILE_PLACEHOLDER)

        self._draw_marker(painter, top_left_x, top_left_y)
        self._draw_attribution(painter)

    def _draw_marker(self, painter, top_left_x, top_left_y):
        if self._marker_lat is None or self._marker_lon is None:
            return
        marker_px_x, marker_px_y = _lonlat_to_pixel(self._marker_lon, self._marker_lat, self._zoom)
        center = QPointF(marker_px_x - top_left_x, marker_px_y - top_left_y)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(MARKER_COLOR.red(), MARKER_COLOR.green(), MARKER_COLOR.blue(), 60))
        painter.drawEllipse(center, MARKER_HALO_RADIUS, MARKER_HALO_RADIUS)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(center, MARKER_RADIUS + MARKER_RING_WIDTH, MARKER_RADIUS + MARKER_RING_WIDTH)
        painter.setBrush(MARKER_COLOR)
        painter.drawEllipse(center, MARKER_RADIUS, MARKER_RADIUS)
        painter.restore()

    def _draw_attribution(self, painter):
        text_rect = painter.fontMetrics().boundingRect(ATTRIBUTION_TEXT).adjusted(-6, -3, 6, 3)
        text_rect.moveBottomRight(self.rect().bottomRight() - QPoint(8, 8))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(13, 17, 23, 190))
        painter.drawRoundedRect(QRectF(text_rect), 4, 4)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(text_rect, Qt.AlignCenter, ATTRIBUTION_TEXT)
        painter.restore()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._last_drag_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        pos = event.position()
        dx = pos.x() - self._last_drag_pos.x()
        dy = pos.y() - self._last_drag_pos.y()
        self._last_drag_pos = pos

        center_px_x, center_px_y = _lonlat_to_pixel(
            self._center_lon, self._center_lat, self._zoom
        )
        self._center_lon, self._center_lat = _pixel_to_lonlat(
            center_px_x - dx, center_px_y - dy, self._zoom
        )
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        old_zoom = self._zoom
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, old_zoom + (1 if event.angleDelta().y() > 0 else -1)))
        if new_zoom == old_zoom:
            return

        cursor_pos = event.position()
        width, height = self.width(), self.height()

        old_center_px_x, old_center_px_y = _lonlat_to_pixel(
            self._center_lon, self._center_lat, old_zoom
        )
        cursor_px_x = old_center_px_x - width / 2.0 + cursor_pos.x()
        cursor_px_y = old_center_px_y - height / 2.0 + cursor_pos.y()
        cursor_lon, cursor_lat = _pixel_to_lonlat(cursor_px_x, cursor_px_y, old_zoom)

        self._zoom = new_zoom
        new_cursor_px_x, new_cursor_px_y = _lonlat_to_pixel(cursor_lon, cursor_lat, new_zoom)
        new_center_px_x = new_cursor_px_x - cursor_pos.x() + width / 2.0
        new_center_px_y = new_cursor_px_y - cursor_pos.y() + height / 2.0
        self._center_lon, self._center_lat = _pixel_to_lonlat(
            new_center_px_x, new_center_px_y, new_zoom
        )
        self.update()
