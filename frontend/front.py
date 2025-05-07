import sys, os
import threading
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtGui import QMovie, QFont, QColor, QPalette
from PyQt5.QtCore import Qt

# Añade la carpeta padre (LEYA-BASE) al path para que encuentre leya.py
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, base_dir)

# 2) Ruta a la carpeta de imágenes
images_dir = os.path.join(base_dir, "imagenes")
# 3) Ruta completa al GIF
gif_path = os.path.join(images_dir, "chromegif.gif")
# Importa tu backend demo.py
from leya import ChromeVoiceAssistant

class AssistantGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        # Instancia del asistente de voz
        self.assistant = ChromeVoiceAssistant()
        self.assistant_thread = None

    def initUI(self):
        # Configuración de la ventana principal
        self.setWindowTitle('Leya - IA Asistente')
        self.setFixedSize(1280, 720)
        # Fondo negro
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(palette)

        # Widget central y layout vertical
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        central_widget.setLayout(layout)

        # GIF animado en el centro
        self.gif_label = QLabel(self)
        self.gif_label.setAlignment(Qt.AlignCenter)
        self.movie = QMovie(gif_path)  # Asegúrate de tener este archivo en el mismo directorio
        self.gif_label.setMovie(self.movie)
        self.movie.start()
        layout.addWidget(self.gif_label)

        # Texto de estado sobre el botón
        self.status_label = QLabel('Status : Standby', self)
        status_font = QFont('Arial', 16)
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet('color: #00e5ff;')  # Tonalidad cian
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Botón de activación
        self.activate_button = QPushButton('ACTIVAR ASISTENTE', self)
        btn_font = QFont('Arial', 14)
        self.activate_button.setFont(btn_font)
        self.activate_button.setFixedSize(220, 45)
        self.activate_button.setStyleSheet(
            'background-color: #1a237e; color: white; border-radius: 8px; padding: 5px;'
        )
        layout.addWidget(self.activate_button)

        # Conecta el botón al método on_activate
        self.activate_button.clicked.connect(self.on_activate)

    def update_status(self, text: str):
        """Actualiza el texto de estado dinámicamente."""
        self.status_label.setText(text)

    def on_activate(self):
        """Inicia el asistente en un hilo separado y actualiza el estado."""
        if self.assistant_thread and self.assistant_thread.is_alive():
            # Si ya está corriendo, ignorar
            return
        # Cambiar estado en interfaz
        self.update_status('Status : Activando...')
        # Crear y arrancar hilo
        self.assistant_thread = threading.Thread(target=self.run_assistant, daemon=True)
        self.assistant_thread.start()

    def run_assistant(self):
        # Ejecuta el backend y actualiza el estado cuando termine
        try:
            self.assistant.run()
        finally:
            # Cuando el asistente termina
            self.update_status('Status : Offline')


def main():
    app = QApplication(sys.argv)
    window = AssistantGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()