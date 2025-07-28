import asyncio
import websockets
import os
import json
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime, timedelta, time
import config

def genera_nome_file(base_path="D:\\downloads", nome_base="encoder_buffer", estensione=".bin"):
    file_path = os.path.join(base_path, f"{nome_base}{estensione}")
    indice = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_path, f"{nome_base} ({indice}){estensione}")
        indice += 1
    return file_path

def crea_grafico_encoder(buffer_array, timestamp, magnitude, status_label):
    try:
        # Verifica lunghezza buffer
        if len(buffer_array) == 0:
            status_label.config(text="Errore: Buffer vuoto")
            return

        # Estrai i campi con la nuova struttura
        infrared = buffer_array & 0x0001
        detect = (buffer_array >> 1) & 0x0001
        door_open = (buffer_array >> 2) & 0x0001
        raw_angle = (buffer_array >> 4) & 0x0FFF

        # Converti raw_angle in gradi
        angles = (raw_angle / 4095) * 360

        # Calcola i timestamp per ogni campione
        ultimo_timestamp = datetime.fromtimestamp(timestamp)
        primo_timestamp = ultimo_timestamp - timedelta(seconds=(len(buffer_array) - 1) * 0.1)
        tempi = [primo_timestamp + timedelta(seconds=i * 0.1) for i in range(len(buffer_array))]

        # Crea il grafico
        plt.figure(figsize=(10, 6))
        plt.plot(tempi, angles, label="Angolo", color="blue")
        plt.plot(tempi, infrared * 10 + 10, label="Infrared", color="red", linestyle="-")
        plt.plot(tempi, detect * 10 + 30, label="Detect", color="green", linestyle="-")
        plt.plot(tempi, door_open * 10 + 50, label="Door Open", color="purple", linestyle="-")

        # Formatta l'asse x
        plt.gca().xaxis.set_major_formatter(DateFormatter("%M:%S"))
        plt.xlabel("Tempo (MM:SS)")
        plt.ylabel("Valori")
        plt.title(f"Dati Encoder - Inizio: {primo_timestamp.strftime('%Y-%m-%d %H:%M:%S')}, Magnitude: {magnitude}")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"Debug: Errore nella creazione del grafico: {e}")
        status_label.config(text=f"Errore: Creazione grafico fallita: {e}")

async def acquisisci_stato_porta_async(status_label):
    uri = config.ESP32_WS_URI
    try:
        status_label.config(text="Stato: Connessione in corso per stato porta...")
        async with websockets.connect(uri, ping_interval=None, ping_timeout=None) as websocket:
            status_label.config(text="Stato: Connesso, richiesta stato porta...")
            print("Debug: Connessione WebSocket stabilita")
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
                            timestamp = time.time()
                            magnitude = 0.0
                            json_received = True
                            status_label.config(text="Avviso: Usati timestamp e magnitude di default")
                        else:
                            return None, None, None

                    message = await asyncio.wait_for(websocket.recv(), timeout=20.0)
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Messaggio ricevuto dopo {elapsed_time:.2f} secondi")
                    if isinstance(message, str):
                        ignored_text_messages += 1
                        print(f"Debug: Ricevuto messaggio testuale #{ignored_text_messages}: {message[:100]}...")
                        if ignored_text_messages > max_ignored_messages:
                            print("Debug: Raggiunto limite di messaggi testuali ignorati")
                            status_label.config(text="Errore: Troppi messaggi testuali ignorati")
                            return None, None, None
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
                    return None, None, None
                except websockets.exceptions.ConnectionClosed as e:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Connessione chiusa inaspettatamente dopo {elapsed_time:.2f} secondi: {e}")
                    status_label.config(text=f"Errore: Connessione chiusa inaspettatamente: {e}")
                    return None, None, None
                except Exception as e:
                    elapsed_time = (datetime.now() - start_time).total_seconds()
                    print(f"Debug: Errore imprevisto dopo {elapsed_time:.2f} secondi: {e}")
                    status_label.config(text=f"Errore: {e}")
                    return None, None, None

            # Elaborazione del buffer e salvataggio del file
            print(f"Debug: Stato finale - buffer_received: {buffer_received}, json_received: {json_received}")
            if buffer_data and timestamp is not None and magnitude is not None:
                # Converti buffer in array numpy di uint16
                buffer_array = np.frombuffer(buffer_data, dtype=np.uint16)
                if len(buffer_array) != 16384:
                    status_label.config(text=f"Errore: Buffer di lunghezza errata ({len(buffer_array)} invece di 16384)")
                    return None, None, None

                # Salva il file con intestazione
                download_path = genera_nome_file()
                num_campioni = len(buffer_data) // 2  # Ogni campione è uint16 (2 byte)
                with open(download_path, "wb") as f:
                    f.write(struct.pack("<Idf", num_campioni, timestamp, magnitude))
                    f.write(buffer_data)
                status_label.config(text=f"Stato: Buffer encoder salvato in {download_path}")

                # Crea il grafico
                crea_grafico_encoder(buffer_array, timestamp, magnitude, status_label)

            return buffer_data, timestamp, magnitude

    except Exception as e:
        print(f"Debug: Errore generale nella connessione: {e}")
        status_label.config(text=f"Errore: {e}")
        return None, None, None

def visualizza_stato_porta_da_file(percorso_file, status_label):
    try:
        status_label.config(text="Stato: Lettura file in corso...")
        with open(percorso_file, "rb") as f:
            # Leggi intestazione
            header = f.read(16)  # 4 (uint32) + 8 (double) + 4 (float)
            if len(header) != 16:
                status_label.config(text="Errore: Intestazione file non valida")
                return
            num_campioni, timestamp, magnitude = struct.unpack("<Idf", header)
            # Leggi dati
            buffer_data = f.read()
            if len(buffer_data) != num_campioni * 2:
                status_label.config(text=f"Errore: Lunghezza dati non valida ({len(buffer_data)} byte invece di {num_campioni * 2})")
                return

        # Converti buffer in array numpy di uint16
        buffer_array = np.frombuffer(buffer_data, dtype=np.uint16)
        if len(buffer_array) != num_campioni:
            status_label.config(text=f"Errore: Buffer di lunghezza errata ({len(buffer_array)} invece di {num_campioni})")
            return

        # Crea il grafico
        crea_grafico_encoder(buffer_array, timestamp, magnitude, status_label)
        status_label.config(text="Stato: Visualizzazione da file completata")

    except Exception as e:
        print(f"Debug: Errore nella lettura del file: {e}")
        status_label.config(text=f"Errore: {e}")

def acquisisci_stato_porta(status_label):
    return asyncio.run(acquisisci_stato_porta_async(status_label))