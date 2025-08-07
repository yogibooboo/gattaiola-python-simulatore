import tkinter as tk
import asyncio
import websockets
import os
import json
import struct
from datetime import datetime
import config

# Flag globale per controllare l'acquisizione continua
running = False

def genera_nome_file(base_path="D:\\downloads\\porta", nome_base="porta", estensione=".bin"):
    """Genera un nome file con timestamp nella directory specificata."""
    os.makedirs(base_path, exist_ok=True)  # Crea la directory se non esiste
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(base_path, f"{nome_base}_{timestamp}{estensione}")
    return file_path

async def acquisisci_stato_porta_async(status_label):
    """Acquisisce lo stato della porta dall'ESP32 e salva il file."""
    uri = config.ESP32_WS_URI
    try:
        status_label.config(text="Stato: Connessione in corso...")
        print("Debug: Connessione WebSocket stabilita")
        async with websockets.connect(uri, ping_interval=None, ping_timeout=None) as websocket:
            status_label.config(text="Stato: Connesso, richiesta stato porta...")
            print("Debug: Invio messaggio 'get_encoder_buffer'")
            await websocket.send("get_encoder_buffer")
            print("Debug: Messaggio 'get_encoder_buffer' inviato")
            status_label.config(text="Stato: Download stato porta in corso...")

            buffer_received = False
            json_received = False
            download_path = None
            buffer_data = None
            timestamp = None
            magnitude = None
            start_time = datetime.now()
            ignored_text_messages = 0
            max_ignored_messages = 5
            max_wait_time = 30.0  # Timeout massimo per ricevere tutti i dati

            while not (buffer_received and json_received):
                try:
                    if (datetime.now() - start_time).total_seconds() > max_wait_time:
                        print("Debug: Timeout massimo raggiunto per ricevere buffer e JSON")
                        status_label.config(text="Errore: Timeout massimo raggiunto")
                        if buffer_received and (timestamp is None or magnitude is None):
                            # Usa valori di default se il JSON non è arrivato
                            timestamp = datetime.now().timestamp()
                            magnitude = 0.0
                            json_received = True
                            status_label.config(text="Avviso: Usati timestamp e magnitude di default")
                        else:
                            return False

                    message = await asyncio.wait_for(websocket.recv(), timeout=20.0)
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Messaggio ricevuto dopo {elapsed_time:.2f} secondi")
                    if isinstance(message, str):
                        ignored_text_messages += 1
                        print(f"Debug: Ricevuto messaggio testuale #{ignored_text_messages}: {message[:100]}...")
                        if ignored_text_messages > max_ignored_messages:
                            print("Debug: Raggiunto limite di messaggi testuali ignorati")
                            status_label.config(text="Errore: Troppi messaggi testuali ignorati")
                            return False
                        try:
                            data = json.loads(message)
                            if "encoder_timestamp" in data and "magnitude" in data:
                                timestamp = data["encoder_timestamp"]
                                magnitude = data["magnitude"]
                                data_leggibile = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                                print(f"Debug: Stato porta acquisito - Data: {data_leggibile}, Magnitude: {magnitude}")
                                status_label.config(text=f"Stato: Dati ricevuti - Data: {data_leggibile}, Magnitude: {magnitude}")
                                json_received = True
                            else:
                                status_label.config(text=f"Stato: Ignorato messaggio testuale #{ignored_text_messages}: {message[:50]}...")
                        except json.JSONDecodeError:
                            status_label.config(text=f"Stato: Ignorato messaggio testuale non JSON #{ignored_text_messages}: {message[:50]}...")
                    else:
                        print(f"Debug: Ricevuto buffer binario di {len(message)} byte")
                        buffer_data = message
                        buffer_received = True

                except asyncio.TimeoutError:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Timeout dopo {elapsed_time:.2f} secondi in attesa dei dati")
                    status_label.config(text="Errore: Timeout in attesa dei dati")
                    return False
                except websockets.exceptions.ConnectionClosed as e:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Connessione chiusa inaspettatamente dopo {elapsed_time:.2f} secondi: {e}")
                    status_label.config(text=f"Errore: Connessione chiusa inaspettatamente: {e}")
                    return False
                except Exception as e:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Errore imprevisto dopo {elapsed_time:.2f} secondi: {e}")
                    status_label.config(text=f"Errore: {e}")
                    return False

            # Elaborazione del buffer e salvataggio del file
            print(f"Debug: Stato finale - buffer_received: {buffer_received}, json_received: {json_received}")
            if buffer_data and timestamp is not None and magnitude is not None:
                # Verifica lunghezza buffer
                if len(buffer_data) != 32768:
                    status_label.config(text=f"Errore: Buffer di lunghezza errata ({len(buffer_data)} invece di 32768)")
                    return False

                # Salva il file con intestazione
                download_path = genera_nome_file()
                num_campioni = len(buffer_data) // 2  # Ogni campione è uint16 (2 byte)
                with open(download_path, "wb") as f:
                    f.write(struct.pack("<Idf", num_campioni, timestamp, magnitude))
                    f.write(buffer_data)
                status_label.config(text=f"Stato: Buffer salvato in {download_path}")
                print(f"Debug: Buffer salvato in {download_path}")
                return True

            return False

    except Exception as e:
        print(f"Debug: Errore generale nella connessione: {e}")
        status_label.config(text=f"Errore: {e}")
        return False

def toggle_acquisizione(status_label, button, window):
    """Avvia o ferma l'acquisizione continua, aggiornando il pulsante e lo stato."""
    global running
    if not running:
        running = True
        button.config(text="Ferma")
        status_label.config(text="Stato: Acquisizione continua avviata")
        print("Debug: Acquisizione continua avviata")
        window.after(0, lambda: loop_continuo(status_label, window))
    else:
        running = False
        button.config(text="Avvia")
        status_label.config(text="Stato: Acquisizione continua fermata")
        print("Debug: Acquisizione continua fermata")

def loop_continuo(status_label, window):
    """Esegue l'acquisizione ogni 30 minuti usando window.after."""
    global running
    if not running:
        status_label.config(text="Stato: Acquisizione continua fermata")
        print("Debug: Loop continuo fermato")
        return

    def run_single_acquisition():
        try:
            # Esegue l'acquisizione in modo sincrono
            success = asyncio.run(acquisisci_stato_porta_async(status_label))
            if success:
                print(f"Debug: Acquisizione completata, file salvato")
                status_label.config(text=f"Stato: Acquisizione completata: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("Debug: Acquisizione fallita")
                status_label.config(text="Errore: Acquisizione fallita")
                running = False
                window.after(0, lambda: toggle_acquisizione(status_label, button, window))
        except Exception as e:
            print(f"Debug: Errore durante acquisizione continua: {e}")
            status_label.config(text=f"Errore: Acquisizione continua fallita: {e}")
            running = False
            window.after(0, lambda: toggle_acquisizione(status_label, button, window))

    run_single_acquisition()
    # Pianifica la prossima acquisizione dopo 30 minuti (1800000 ms)
    if running:
        window.after(1800000, lambda: loop_continuo(status_label, window))
        window.update()

# Crea la GUI
window = tk.Tk()
window.title("Acquisizione Continua Porta")

status_label = tk.Label(window, text="Stato: Inattivo")
status_label.grid(row=0, column=0, padx=5, pady=5)

button = tk.Button(window, text="Avvia", command=lambda: toggle_acquisizione(status_label, button, window))
button.grid(row=1, column=0, padx=5, pady=5)

window.mainloop()