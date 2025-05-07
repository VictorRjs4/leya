import speech_recognition as sr
import pyttsx3
import pyautogui
import webbrowser
import subprocess
import time
import os
import keyboard
import logging
import numpy as np  
import re
import pyperclip
import sqlite3
from difflib import get_close_matches
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.stem import SnowballStemmer


# Audio control (requires 'pycaw' and 'comtypes')
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    AUDIO_ENABLED = True
except ImportError:
    AUDIO_ENABLED = False
    logging.warning("Audio control disabled: install with 'pip install pycaw comtypes'")

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ChromeVoiceAssistant:
    def __init__(self):
        # Voz a texto
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.0
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

        # Texto a voz
        self.engine = pyttsx3.init()
        for voice in self.engine.getProperty('voices'):
            if 'spanish' in voice.id.lower():
                self.engine.setProperty('voice', voice.id)
                break
        self.engine.setProperty('rate', 150)
        self.engine.setProperty('volume', 1.0)

        # Estado
        self.chrome_opened = False
        self.last_suggestion = None

        # Audio endpoint (pycaw)
        if AUDIO_ENABLED:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume_ctrl = cast(interface, POINTER(IAudioEndpointVolume))

        # Procesamiento de lenguaje
        self.stemmer = SnowballStemmer('spanish')
        self.vectorizer = TfidfVectorizer(tokenizer=self.preprocess_text, ngram_range=(1,2))

        # Mapas de acciones
        self.websites = {
            'correo': 'https://mail.google.com',
            'youtube': 'https://www.youtube.com',
            'facebook': 'https://www.facebook.com',
            'whatsapp': 'https://web.whatsapp.com',
            'drive': 'https://drive.google.com',
            'maps': 'https://maps.google.com',
            'noticias': 'https://news.google.com',
            'traductor': 'https://translate.google.com'
        }
        self.command_actions = {
            'abrir chrome': self.open_chrome,
            'nueva pestaña': lambda: self._shortcut(['ctrl','t'], 'Nueva pestaña'),
            'cerrar pestaña': lambda: self._shortcut(['ctrl','w'], 'Pestaña cerrada'),
            'reabrir pestaña': lambda: self._shortcut(['ctrl','shift','t'], 'Pestaña restaurada'),
            'volver': lambda: self._shortcut(['alt','left'], 'Volviendo atrás'),
            'adelante': lambda: self._shortcut(['alt','right'], 'Avanzando'),
            'recargar': lambda: self._shortcut(['f5'], 'Recargando'),
            'pantalla completa': lambda: self._shortcut(['f11'], 'Alternando pantalla completa'),
            'acercar pantalla': lambda: self._shortcut(['ctrl','+'], 'Acercando'),
            'alejar pantalla': lambda: self._shortcut(['ctrl','-'], 'Alejando'),
            'captura de pantalla': self.take_screenshot,
            'sube un poco': lambda: self._scroll(300, 'Subiendo un poco'),
            'baja un poco': lambda: self._scroll(-300, 'Bajando un poco'),
            'crear comando': self.create_custom_command,
        }
        # Crear base de datos de comandos personalizados
        self.create_database()
        
        # Preparar lista de comandos
        self.update_command_list()
        self._train_model()

    def update_command_list(self):
        """Actualiza la lista de comandos incluyendo los personalizados"""
        # Comandos básicos
        self.all_commands = list(self.command_actions.keys()) + [f'abrir {s}' for s in self.websites] + ['buscar', 'confirmo']
        
        # Añadir comandos personalizados de la base de datos
        try:
            conn = sqlite3.connect('commands.db')
            c = conn.cursor()
            c.execute('SELECT command FROM commands')
            custom_commands = [row[0] for row in c.fetchall()]
            conn.close()
            self.all_commands.extend(custom_commands)
        except Exception as e:
            logging.error(f"Error al cargar comandos personalizados: {e}")

    def preprocess_text(self, text):
        """Preprocesa el texto para análisis lingüístico"""
        tokens = re.findall(r"\b\w+\b", text.lower())
        return [self.stemmer.stem(t) for t in tokens]

    def create_database(self):
        """Crea la base de datos y la tabla de comandos personalizados"""
        try:
            conn = sqlite3.connect('commands.db')
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    url TEXT NOT NULL
                )
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error al crear base de datos: {e}")

    def add_custom_command(self, name, url):
        try:
            conn = sqlite3.connect('commands.db')
            c = conn.cursor()
            c.execute('INSERT INTO commands (command, url) VALUES (?, ?)', (name, url))
            conn.commit()
            conn.close()
            logging.info('Comando personalizado agregado: %s', name)
            self.update_command_list()
            self._train_model()
            return True
        except Exception as e:
            logging.error(f"Error al agregar comando: {e}")
            return False

    def create_custom_command(self):
        """Función para crear un nuevo comando personalizado"""
        self.speak('¿Quieres crear un comando para la página en la que te encuentras?')
        resp = self.listen(timeout=10)

        if any(token in resp for token in ('sí', 'si', 'claro', 'vale', 'por supuesto')):
            # Pedir nombre
            self.speak('¿Qué nombre le quieres poner?')
            name = self.listen(timeout=10).strip()

            # Copiar URL actual de Chrome
            self.speak(f'Has elegido "{name}". Copiando la URL de la pestaña activa…')
            if not self.chrome_opened:
                self.open_chrome()
            else:
                self._focus_chrome()

            pyautogui.hotkey('ctrl', 'l')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.1)
            url = pyperclip.paste().strip()

            if self.add_custom_command(name, url):
                self.speak(f'Comando {name} agregado correctamente')
            else:
                self.speak('Hubo un error al crear el comando')
        else:
            self.speak('Comando no creado')

        return True

#-----------------------------------------------
    def _train_model(self):
        """Entrena el modelo de vectorización para reconocimiento de comandos"""
        try:
            self.vectorizer.fit(self.all_commands)
            self.command_vectors = self.vectorizer.transform(self.all_commands)
            logging.info('Modelo IA entrenado con %d comandos', len(self.all_commands))
        except Exception as e:
            logging.error(f"Error al entrenar modelo: {e}")

    def _find_best_match(self, cmd):
        """Encuentra el mejor comando que coincide con el texto proporcionado"""
        try:
            vec = self.vectorizer.transform([cmd])
            sims = cosine_similarity(vec, self.command_vectors)[0]
            idx, conf = int(np.argmax(sims)), float(max(sims))
            if conf > 0.5:
                return self.all_commands[idx], conf
            m = get_close_matches(cmd, self.all_commands, n=1, cutoff=0.6)
            return (m[0], 0.6) if m else (None, 0)
        except Exception as e:
            logging.error(f"Error al buscar coincidencia: {e}")
            return None, 0

    def speak(self, text):
        """Convierte texto a voz"""
        try:
            logging.info('Leya dice: %s', text)
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            logging.error(f"Error en sintetizador de voz: {e}")

    def listen(self, timeout=5):
        """Escucha y reconoce voz del usuario"""
        try:
            with sr.Microphone() as src:
                self.recognizer.adjust_for_ambient_noise(src, duration=0.5)
                try:
                    audio = self.recognizer.listen(src, timeout=timeout, phrase_time_limit=5)
                except sr.WaitTimeoutError:
                    return ''
            try:
                return self.recognizer.recognize_google(audio, language='es-ES').lower()            
            except:
                return ''
        except Exception as e:
            logging.error(f"Error en reconocimiento de voz: {e}")
            return ''

    def open_chrome(self):
        """Abre Google Chrome o lo enfoca si ya está ejecutándose"""
        try:
            if self._is_running('chrome.exe'):
                self._focus_chrome()
                self.speak('Chrome ya abierto, enfocado')
                self.chrome_opened = True
                return
            paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
            ]
            for p in paths:
                if os.path.exists(p):
                    subprocess.Popen([p, '--start-maximized'])
                    time.sleep(1)
                    self.chrome_opened = True
                    self.speak('Abriendo Chrome')
                    return
            # Fallback al navegador predeterminado
            webbrowser.open('https://www.google.com')
            self.chrome_opened = True
            self.speak('Abriendo navegador')
        except Exception as e:
            logging.error(f"Error al abrir Chrome: {e}")
            self.speak('No pude abrir Chrome')

    def _is_running(self, proc):
        """Verifica si un proceso está ejecutándose"""
        try:
            out = subprocess.check_output('tasklist', shell=True).decode('cp1252')
            return proc in out
        except Exception as e:
            logging.error(f"Error al verificar proceso: {e}")
            return False

    def _focus_chrome(self):
        """Enfoca la ventana de Chrome"""
        try:
            subprocess.Popen([
                'powershell','-Command',
                "(New-Object -ComObject Shell.Application).Windows()"
                "|Where-Object {$_.Name -like '*Chrome*'}"
                "|ForEach-Object {$_.Visible = $True}"
            ])
        except Exception as e:
            logging.error(f"Error al enfocar Chrome: {e}")

    def _shortcut(self, keys, msg=None):
        """Ejecuta un atajo de teclado"""
        try:
            if not self.chrome_opened:
                self.open_chrome()
            else:
                self._focus_chrome()
            pyautogui.hotkey(*keys)
            if msg:
                self.speak(msg)
            time.sleep(0.2)
        except Exception as e:
            logging.error(f"Error al ejecutar atajo: {e}")

    def _scroll(self, amount, msg=None):
        """Realiza desplazamiento vertical"""
        try:
            pyautogui.scroll(amount)
            if msg:
                self.speak(msg)
            time.sleep(0.2)
        except Exception as e:
            logging.error(f"Error al desplazar: {e}")

    def take_screenshot(self):
        """Toma una captura de pantalla"""
        try:
            path = os.path.join(os.path.expanduser('~'), 'Desktop', 'capture.png')
            pyautogui.screenshot(path)
            self.speak(f'Captura guardada en {path}')
        except Exception as e:
            logging.error(f"Error al tomar captura: {e}")
            self.speak('No pude tomar la captura')

    def set_volume(self, level):
        """Establece el volumen del sistema"""
        if not AUDIO_ENABLED:
            self.speak('Funcionalidad de volumen no disponible')
            return
        try:
            lvl = max(0, min(level, 100)) / 100.0
            self.volume_ctrl.SetMasterVolumeLevelScalar(lvl, None)
            self.speak(f'Volumen ajustado a {int(lvl*100)}')
        except Exception as e:
            logging.error(f"Error al ajustar volumen: {e}")
            self.speak('No pude ajustar el volumen')

    def change_volume(self, delta):
        """Cambia el volumen en un incremento/decremento"""
        if not AUDIO_ENABLED:
            self.speak('Funcionalidad de volumen no disponible')
            return
        try:
            curr = self.volume_ctrl.GetMasterVolumeLevelScalar()
            new = max(0, min(curr + delta, 1))
            self.volume_ctrl.SetMasterVolumeLevelScalar(new, None)
            self.speak(f'Volumen ahora {int(new*100)}')
        except Exception as e:
            logging.error(f"Error al cambiar volumen: {e}")
            self.speak('No pude cambiar el volumen')

    def process_command(self, command):
        """Procesa un comando de voz y ejecuta la acción correspondiente"""
        try:
            # Verificar confirmación de sugerencia anterior
            if 'confirmo' in command and self.last_suggestion:
                command = self.last_suggestion
                self.last_suggestion = None
                self.speak(f'Ejecutando {command}')
            
            # Verificar comandos de salida
            if any(k in command for k in ['adiós', 'apagar sistema', 'cerrar sistema']):
                self.speak('Hasta luego')
                return False
            
            # Verificar comandos para abrir sitios web
            for site, url in self.websites.items():
                if f'abrir {site}' in command:
                    if not self.chrome_opened:
                        self.open_chrome()
                    webbrowser.open(url)
                    self.speak(f'Abriendo {site}')
                    return True
            
            # Verificar comandos directos
            for key, act in self.command_actions.items():
                if key in command:
                    act()
                    return True
            
               # Caso especial: selecciona <texto>
            if command.startswith('selecciona '):
                return self.select_by_title(command)

        # Comandos directos
            for key, action in self.command_actions.items():
                if key == 'selecciona':
                 continue
            if key in command:
                action()
                return True



            
            # Comandos de búsqueda
            if 'buscar' in command:
                q = command.split('buscar')[-1].strip()
                if not self.chrome_opened:
                    self.open_chrome()
                webbrowser.open(f'https://www.google.com/search?q={q}')
                self.speak(f'Buscando {q}')
                return True
            
            # Comandos de volumen específico
            m = re.search(r'(?:sube|aumenta).*volumen a (\d+)', command)
            if m:
                self.set_volume(int(m.group(1)))
                return True
            m = re.search(r'(?:baja|disminuye).*volumen a (\d+)', command)
            if m:
                self.set_volume(int(m.group(1)))
                return True
            
            # Comandos de ajuste de volumen
            if any(k in command for k in ['sube volumen', 'más volumen', 'aumentar volumen']):
                self.change_volume(0.05)
                return True
            if any(k in command for k in ['baja volumen', 'menos volumen', 'disminuir volumen']):
                self.change_volume(-0.05)
                return True
            
            # Comandos para videos en pantalla completa
            if any(k in command for k in ['video pantalla completa', 'pantalla completa video', 'expandir video']):
                w, h = pyautogui.size()
                pyautogui.click(w/2, h/2)
                time.sleep(0.1)
                pyautogui.press('f')
                self.speak('Video pantalla completa')
                return True
            
            if any(k in command for k in ['cerrar pantalla completa', 'salir video pantalla completa', 'escapar video']):
                pyautogui.press('esc')
                self.speak('Saliendo de pantalla completa')
                return True
            
            # Comandos personalizados desde base de datos
            try:
                conn = sqlite3.connect('commands.db')
                c = conn.cursor()
                c.execute('SELECT url FROM commands WHERE command = ?', (command,))
                result = c.fetchone()
                conn.close()
                
                if result:
                    webbrowser.open(result[0])
                    self.speak(f'Abriendo {command}')
                    return True
            except Exception as e:
                logging.error(f"Error al buscar comando personalizado: {e}")
            
            # Buscar mejor coincidencia si no se encontró comando directo
            best, conf = self._find_best_match(command)
            if best:
                if conf > 0.7:
                    return self.process_command(best)
                else:
                    self.speak(f'Quisiste decir {best}? Di confirmo')
                    self.last_suggestion = best
                    return True
            
            self.speak('No entendí, repite por favor')
            return True
        except Exception as e:
            logging.error(f"Error al procesar comando: {e}")
            self.speak('Hubo un error al procesar tu comando')
            return True
        

    def run(self):
        """Inicia el asistente de voz"""
        try:
            self.speak('Hola soy Leya, di surge para comenzar')
            while True:
                cmd = self.listen(timeout=10)
                if not cmd:
                    continue
                    
                # Modo básico: comandos con 'surge'
                if 'surge' in cmd:
                    self.speak('¿En qué puedo ayudarte?')
                    command_timeout = time.time() + 60  # 1 minuto de tiempo límite
                    
                    while time.time() < command_timeout:
                        cmd2 = self.listen(timeout=5)
                        if not cmd2:
                            continue
                        
                        # Renovar tiempo si hay actividad
                        command_timeout = time.time() + 60
                        
                        if not self.process_command(cmd2):
                            break
        except KeyboardInterrupt:
            self.speak('Adiós')
        except Exception as e:
            logging.error(f"Error crítico: {e}")
            self.speak('Ocurrió un error en el sistema')

if __name__ == '__main__':
    assistant = ChromeVoiceAssistant()
    try:
        assistant.run()
    except KeyboardInterrupt:
        assistant.speak('Adiós') 