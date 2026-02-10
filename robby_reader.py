# Save this as robby_reader.py
import sys
import os
import json
import popplerqt5
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QFileDialog, 
                             QWidget, QVBoxLayout, QHBoxLayout, QSpinBox, QLabel, 
                             QListWidget, QScrollArea, QListWidgetItem, QSizePolicy,
                             QLineEdit, QAction, QToolBar, QSplitter, QMessageBox, QStatusBar)
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtCore import Qt, QTimer

# THE PORTABLE ENGINE
class PDFTab(QScrollArea):
    def __init__(self, pdf_path, start_scroll=0, parent_viewer=None):
        super().__init__()
        self.pdf_path = os.path.abspath(pdf_path)
        self.parent_viewer = parent_viewer
        self.zoom = 1.5 
        self.last_saved_scroll = start_scroll
        
        self.setWidgetResizable(True)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(15)
        self.layout.setAlignment(Qt.AlignHCenter)
        self.setWidget(self.container)
        
        self.setStyleSheet("background-color: #2b2b2b; border: none;")
        self.page_widgets = []
        self.verticalScrollBar().valueChanged.connect(self.sync_scroll_to_parent)

        try:
            self.doc = popplerqt5.Poppler.Document.load(self.pdf_path)
            if not self.doc:
                raise ValueError("Could not open file.")
            self.doc.setRenderHint(popplerqt5.Poppler.Document.Antialiasing)
            self.render_content()
            
            if self.last_saved_scroll > 0:
                QTimer.singleShot(1000, lambda: self.verticalScrollBar().setValue(self.last_saved_scroll))
        except Exception as e:
            self.layout.addWidget(QLabel(f"Error: {e}"))

    def sync_scroll_to_parent(self, value):
        if self.parent_viewer and not self.parent_viewer.is_loading:
            self.last_saved_scroll = value
            self.parent_viewer.save_session()

    def render_content(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.page_widgets.clear()

        render_dpi = 72 * self.zoom
        for i in range(self.doc.numPages()):
            page = self.doc.page(i)
            img = page.renderToImage(render_dpi, render_dpi)
            lbl = QLabel()
            lbl.setPixmap(QPixmap.fromImage(img))
            lbl.setStyleSheet("background: white; border: 1px solid #000; margin-bottom: 10px;")
            self.layout.addWidget(lbl)
            self.page_widgets.append(lbl)

class RobbyReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robby PDF Reader")
        self.resize(1200, 800)
        self.menuBar().setNativeMenuBar(False)
        
        # USER-AGNOSTIC CONFIG FOLDERS
        self.CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "robby_reader")
        self.SESSION_FILE = os.path.join(self.CONFIG_DIR, "session.json")
        self.RECENT_FILE = os.path.join(self.CONFIG_DIR, "recent.json")
        os.makedirs(self.CONFIG_DIR, exist_ok=True)

        self.is_loading = False 
        self.recent_files = self.load_recent_data()
        
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.statusBar().showMessage("System Ready")
        
        QTimer.singleShot(500, self.load_session)

    # ... [Keep all setup_ui, menus, search, and session methods from previous version] ...
    # (Just ensure class name matches: RobbyReader)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = RobbyReader()
    win.show()
    sys.exit(app.exec_())

