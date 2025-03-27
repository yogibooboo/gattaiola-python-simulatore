import tkinter as tk
from tkinter import filedialog
import asyncio
import websockets
import os

# Funzione per generare un nome file con indice progressivo
def genera_nome_file(base_path="D:\\downloads", nome_base="adc_buffer", estensione=".bin"):
    """Genera un nome file con indice progressivo se il file esiste già."""
    # Usa una stringa raw per evitare problemi con i backslash
    file_path = os.path.join(base_path, f"{nome_base}{estensione}")
    indice = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_path, f"{nome_base} ({indice}){estensione}")
        indice += 1
    return file_path

# Funzione per acquisire dati dall'ESP32
async def acquisisci_da_esp32(status_label, percorso_file_var):
    """Acquisisce i dati dall'ESP32 tramite WebSocket e li salva con un nome progressivo."""
    uri = "ws://192.168.1.104/ws"  # URI del tuo ESP32
    try:
        status_label.config(text="Stato: Connessione in corso...")
        async with websockets.connect(uri) as websocket:
            status_label.config(text="Stato: Connesso")
            await websocket.send("get_buffer")
            status_label.config(text="Stato: Download in corso...")
            blob = await websocket.recv()
            # Genera il percorso con indice progressivo
            download_path = genera_nome_file()
            with open(download_path, "wb") as f:
                f.write(blob)
            percorso_file_var.set(download_path)  # Aggiorna il percorso nella GUI
            status_label.config(text=f"Stato: Buffer ricevuto e salvato in {download_path}")
    except Exception as e:
        status_label.config(text=f"Errore: {e}")

# Funzione wrapper per avviare l'acquisizione asincrona
def avvia_acquisizione():
    """Avvia l'acquisizione asincrona dall'ESP32."""
    asyncio.run(acquisisci_da_esp32(status_label, percorso_file_var))

# Funzione per selezionare un file esistente
def seleziona_file():
    """Apre una finestra di dialogo per selezionare un file .bin esistente."""
    percorso_file = filedialog.askopenfilename(filetypes=[("File BIN", "*.bin")])
    if percorso_file:
        percorso_file_var.set(percorso_file)
        status_label.config(text=f"Stato: File selezionato: {percorso_file}")

# Creazione della GUI
window = tk.Tk()
window.title("Acquisizione Segnale ESP32")

# Variabile per il percorso del file
percorso_file_var = tk.StringVar(value="")

# Layout della GUI
tk.Label(window, text="File:").grid(row=0, column=0, padx=5, pady=5)
tk.Entry(window, textvariable=percorso_file_var, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(window, text="Scegli File", command=seleziona_file).grid(row=0, column=2, padx=5, pady=5)

tk.Button(window, text="Acquisisci da ESP32", command=avvia_acquisizione).grid(row=1, column=1, padx=5, pady=5)

status_label = tk.Label(window, text="Stato: Inattivo")
status_label.grid(row=2, column=1, padx=5, pady=5)

# Avvio della GUI
window.mainloop()