#!/usr/bin/env python3
# Robby Reader v1.0 - Open Source Multi-tab PDF Viewer
# License: MIT | Author: Fred

import sys
import os
import json

# Ensure dependencies are handled gracefully
try:
    import popplerqt5
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QFileDialog, 
                                 QWidget, QVBoxLayout, QHBoxLayout, QSpinBox, QLabel, 
                                 QListWidget, QScrollArea, QListWidgetItem, QSizePolicy,
                                 QLineEdit, QAction, QToolBar, QSplitter, QMessageBox, QStatusBar)
    from PyQt5.QtGui import QPixmap, QKeySequence
    from PyQt5.QtCore import Qt, QTimer
except ImportError as e:
    print(f"Error: Missing dependencies. Please install: sudo apt install python3-pyqt5 python3-poppler-qt5\n{e}")
    sys.exit(1)

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
                raise Exception("File could not be opened.")
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
        
        # PORTABLE CONFIG DIRECTORY
        self.CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "robby_reader")
        self.SESSION_FILE = os.path.join(self.CONFIG_DIR, "session.json")
        self.RECENT_FILE = os.path.join(self.CONFIG_DIR, "recent.json")
        os.makedirs(self.CONFIG_DIR, exist_ok=True)

        self.is_loading = False 
        self.recent_files = self.load_recent_data()
        
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.statusBar().showMessage("System Online")
        
        QTimer.singleShot(500, self.load_session)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.toc_list = QListWidget()
        self.toc_list.setFixedWidth(280)
        self.toc_list.itemClicked.connect(self.on_toc_click)
        
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.sync_ui)
        self.tabs.currentChanged.connect(self.update_status)
        
        self.splitter.addWidget(self.toc_list)
        self.splitter.addWidget(self.tabs)
        main_layout.addWidget(self.splitter)

    def setup_menus(self):
        self.menuBar().clear()
        file_m = self.menuBar().addMenu("&File")
        file_m.addAction("Open PDF", self.open_file, QKeySequence.Open)
        self.recent_menu = file_m.addMenu("Recent Files")
        self.update_recent_menu()
        file_m.addSeparator()
        file_m.addAction("Exit", self.close, "Ctrl+Q")

        edit_m = self.menuBar().addMenu("&Edit")
        edit_m.addAction("Find...", lambda: self.search_in.setFocus(), QKeySequence.Find)
        edit_m.addAction("Clear Session", self.clear_session, "Ctrl+Shift+Del")

        view_m = self.menuBar().addMenu("&View")
        view_m.addAction("Zoom In", lambda: self.adjust_zoom(0.2), QKeySequence.ZoomIn)
        view_m.addAction("Zoom Out", lambda: self.adjust_zoom(-0.2), QKeySequence.ZoomOut)

    def setup_toolbar(self):
        self.toolbar = QToolBar("Controls")
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self.toolbar.addAction("-", lambda: self.adjust_zoom(-0.2))
        self.toolbar.addAction("+", lambda: self.adjust_zoom(0.2))
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.spin = QSpinBox(); self.spin.setRange(1, 9999)
        self.spin.editingFinished.connect(self.manual_go)
        self.toolbar.addWidget(QLabel(" Page: "))
        self.toolbar.addWidget(self.spin)
        self.total_lbl = QLabel(" / 0 ")
        self.toolbar.addWidget(self.total_lbl)
        spacer2 = QWidget(); spacer2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer2)
        self.search_in = QLineEdit(); self.search_in.setPlaceholderText("Find...")
        self.search_in.returnPressed.connect(lambda: self.perform_search(True))
        self.toolbar.addWidget(self.search_in)
        self.toolbar.addAction("▲", lambda: self.perform_search(False))
        self.toolbar.addAction("▼", lambda: self.perform_search(True))

    def perform_search(self, forward=True):
        query = self.search_in.text().strip()
        cur = self.tabs.currentWidget()
        if not query or not cur: return
        current_p = self.spin.value() - 1
        num_pages = cur.doc.numPages()
        pages = list(range(current_p + 1, num_pages)) + list(range(0, current_p + 1)) if forward else list(range(current_p - 1, -1, -1)) + list(range(num_pages - 1, current_p - 1, -1))
        for i in pages:
            page = cur.doc.page(i)
            if page.search(query, popplerqt5.Poppler.Page.IgnoreCase) or query.lower() in page.text(page.pageSize().toRect()).lower():
                self.spin.setValue(i + 1); self.manual_go()
                return
        self.statusBar().showMessage(f"'{query}' not found", 2000)

    def open_file(self, path=None, scroll=0):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF (*.pdf)")
        if path and os.path.exists(path):
            self.save_recent_data(path)
            for i in range(self.tabs.count()):
                if self.tabs.widget(i).pdf_path == path:
                    self.tabs.setCurrentIndex(i); return
            tab = PDFTab(path, scroll, self)
            idx = self.tabs.addTab(tab, os.path.basename(path))
            self.tabs.setCurrentIndex(idx); self.save_session()

    def update_status(self):
        cur = self.tabs.currentWidget()
        if cur: self.statusBar().showMessage(f"Zoom: {int(cur.zoom*100)}% | {cur.pdf_path}")

    def save_recent_data(self, path):
        if path in self.recent_files: self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        with open(self.RECENT_FILE, "w") as f: json.dump(self.recent_files, f)
        self.update_recent_menu()

    def load_recent_data(self):
        if os.path.exists(self.RECENT_FILE):
            try:
                with open(self.RECENT_FILE, "r") as f: return json.load(f)
            except: pass
        return []

    def update_recent_menu(self):
        self.recent_menu.clear()
        for p in self.recent_files:
            a = QAction(os.path.basename(p), self)
            a.triggered.connect(lambda checked, path=p: self.open_file(path))
            self.recent_menu.addAction(a)

    def sync_ui(self, index):
        cur = self.tabs.widget(index)
        if cur:
            self.total_lbl.setText(f" / {cur.doc.numPages()} ")
            self.load_toc(cur.doc)

    def load_toc(self, doc):
        self.toc_list.clear()
        root = doc.toc()
        if root: self._walk_native_toc(root)

    def _walk_native_toc(self, container):
        for i in range(container.numChildren()):
            child = container.child(i)
            it = QListWidgetItem(child.text())
            if child.destination(): it.setData(Qt.UserRole, child.destination().pageNumber())
            self.toc_list.addItem(it)
            if child.numChildren() > 0: self._walk_native_toc(child)

    def on_toc_click(self, item):
        p = item.data(Qt.UserRole)
        if p is not None: self.spin.setValue(p + 1); self.manual_go()

    def manual_go(self):
        cur = self.tabs.currentWidget()
        p = self.spin.value() - 1
        if cur and 0 <= p < len(cur.page_widgets):
            cur.verticalScrollBar().setValue(cur.page_widgets[p].pos().y())

    def adjust_zoom(self, delta):
        cur = self.tabs.currentWidget()
        if cur:
            vbar = cur.verticalScrollBar()
            ratio = vbar.value() / max(1, vbar.maximum())
            cur.zoom = max(0.5, cur.zoom + delta); cur.render_content()
            QTimer.singleShot(300, lambda: vbar.setValue(int(ratio * vbar.maximum())))
            self.update_status()

    def clear_session(self):
        if os.path.exists(self.SESSION_FILE): os.remove(self.SESSION_FILE)
        self.tabs.clear(); self.statusBar().showMessage("Session Cleared", 2000)

    def close_tab(self, index):
        self.tabs.removeTab(index); self.save_session()

    def save_session(self):
        if self.is_loading: return
        data = [{"path": self.tabs.widget(i).pdf_path, "scroll": self.tabs.widget(i).verticalScrollBar().value()} for i in range(self.tabs.count())]
        with open(self.SESSION_FILE, "w") as f: json.dump(data, f)

    def load_session(self):
        if not os.path.exists(self.SESSION_FILE): return
        self.is_loading = True
        try:
            with open(self.SESSION_FILE, "r") as f:
                for item in json.load(f):
                    if os.path.exists(item['path']): self.open_file(item['path'], item.get('scroll', 0))
        except: pass
        finally: self.is_loading = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = RobbyReader()
    win.show()
    sys.exit(app.exec_())

