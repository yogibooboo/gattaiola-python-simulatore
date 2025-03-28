import tkinter as tk
from tkinter import filedialog
import asyncio
import websockets
import os
import struct
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import analisiESP32  # Import del nuovo modulo

# Funzione per generare un nome file con indice progressivo
def genera_nome_file(base_path="D:\\downloads", nome_base="adc_buffer", estensione=".bin"):
    """Genera un nome file con indice progressivo se il file esiste già."""
    file_path = os.path.join(base_path, f"{nome_base}{estensione}")
    indice = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_path, f"{nome_base} ({indice}){estensione}")
        indice += 1
    return file_path

# Funzione per acquisire dati dall'ESP32
async def acquisisci_da_esp32(status_label, percorso_file_var):
    """Acquisisci i dati dall'ESP32 tramite WebSocket e li salva con un nome progressivo."""
    uri = "ws://192.168.1.104/ws"  # URI del tuo ESP32
    try:
        status_label.config(text="Stato: Connessione in corso...")
        async with websockets.connect(uri) as websocket:
            status_label.config(text="Stato: Connesso")
            await websocket.send("get_buffer")
            status_label.config(text="Stato: Download in corso...")
            blob = await websocket.recv()
            download_path = genera_nome_file()
            with open(download_path, "wb") as f:
                f.write(blob)
            percorso_file_var.set(download_path)
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

# Funzione per la media scorrevole
def media_scorrevole(segnale, larghezza_finestra):
    """Applica una media scorrevole al segnale."""
    finestra = np.ones(larghezza_finestra) / larghezza_finestra
    return np.convolve(segnale, finestra, mode='same')

# Funzione per la sincronizzazione BMC
def sincronizza_bmc(segnale, periodo_bit):
    """Calcola la correlazione e trova i picchi."""
    forma_onda_ideale = np.concatenate([np.ones(periodo_bit // 2), -np.ones(periodo_bit // 2)])
    correlazione = np.correlate(segnale, forma_onda_ideale, mode='same')
    picchi, _ = find_peaks(np.abs(correlazione), prominence=0.5)
    return correlazione, picchi

# Funzione per calcolare il CRC-16-CCITT
def calc_crc16_ccitt(data):
    """Calcola il CRC-16-CCITT."""
    crc = 0x0  # Valore iniziale
    polynomial = 0x1021
    for byte in data:
        b = byte
        for i in range(8):
            bit = ((b >> i) & 1) == 1
            c15 = ((crc >> 15) & 1) == 1
            crc <<= 1
            if c15 ^ bit:
                crc ^= polynomial
        crc &= 0xffff
    crc_reversed = 0
    for i in range(16):
        if (crc >> i) & 1:
            crc_reversed |= 1 << (15 - i)
    return crc_reversed

# Funzione per decodificare i bit e i byte
def decodifica_segnale(picchi, correlazione, periodo_bit_campioni):
    """Decodifica i picchi in bit e poi in byte, verificando il CRC."""
    distanze = np.diff(picchi)
    soglia_mezzo_bit = periodo_bit_campioni * 3 // 4
    bits = []
    i = 0
    while i < len(distanze):
        if distanze[i] < soglia_mezzo_bit:
            if i + 1 < len(distanze) and distanze[i + 1] < soglia_mezzo_bit:
                bits.append(0)
                i += 2
            else:
                i += 1
        else:
            bits.append(1)
            i += 1

    # Trova la sequenza di sincronizzazione (10 bit a 0)
    for i in range(len(bits) - 9):
        if all(bit == 0 for bit in bits[i:i + 10]):
            indice_partenza = i + 10
            break
    else:
        return bits, None, None, None, None

    # Decodifica dei byte
    bytes_decodificati = []
    for i in range(10):
        indice_byte = indice_partenza + i * 9
        if indice_byte + 9 > len(bits):
            return bits, None, None, None, None
        if bits[indice_byte] != 1:
            return bits, None, None, None, indice_byte
        byte = 0
        for j in range(8):
            byte |= bits[indice_byte + 1 + j] << j
        bytes_decodificati.append(byte)

    # Verifica CRC
    dati = bytes_decodificati[:-2]
    crc_ricevuto = (bytes_decodificati[-1] << 8) | bytes_decodificati[-2]
    crc_calcolato = calc_crc16_ccitt(dati)
    crc_ok = crc_ricevuto == crc_calcolato

    return bits, bytes_decodificati, crc_ricevuto, crc_calcolato, crc_ok

# Funzione per visualizzare il file
def visualizza_file():
    """Visualizza il segnale, la correlazione con i bit decodificati sopra i picchi e decodifica i byte con CRC."""
    percorso_file = percorso_file_var.get()
    if not percorso_file or not os.path.exists(percorso_file):
        status_label.config(text="Errore: Nessun file selezionato o file non trovato")
        return

    # Leggi il file binario
    with open(percorso_file, "rb") as f:
        data = f.read()
    segnale_normalizzato = np.array(struct.unpack("<" + "h" * (len(data) // 2), data))

    # Parametri di campionamento
    periodo_campionamento = 1 / 134.2e3 * 1e6
    durata_bit = 1 / (134.2e3 / 32) * 1e6
    campioni_per_bit = int(durata_bit / periodo_campionamento)
    larghezza_finestra = int((durata_bit / 4) / periodo_campionamento)

    # Filtraggio (opzionale in base al checkbox)
    if media_scorrevole_var.get():  # Se il checkbox è selezionato
        segnale_filtrato = media_scorrevole(segnale_normalizzato, larghezza_finestra)
    else:
        segnale_filtrato = segnale_normalizzato  # Passa il segnale inalterato
    segnale_filtrato = np.nan_to_num(segnale_filtrato)

    # Correlazione e picchi
    correlazione, picchi = sincronizza_bmc(segnale_filtrato, campioni_per_bit)

    # Decodifica
    bits, bytes_decodificati, crc_ricevuto, crc_calcolato, crc_ok = decodifica_segnale(picchi, correlazione, campioni_per_bit)

    # Pulizia degli assi
    ax1.clear()
    ax2.clear()

    # Grafico 1: Segnale normalizzato
    ax1.plot(segnale_normalizzato, label=f"Segnale Normalizzato\nCampioni/bit: {campioni_per_bit}")
    for i in range(0, len(segnale_normalizzato), campioni_per_bit):
        ax1.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax1.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax1.set_title('Segnale Normalizzato')
    ax1.legend()

    # Grafico 2: Correlazione, picchi e numeri dei bit
    ax2.plot(correlazione, label='Correlazione')
    ax2.plot(picchi, correlazione[picchi], "x", label='Picchi')
    for i in range(0, len(correlazione), campioni_per_bit):
        ax2.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax2.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)

    # Visualizzazione dei bit come numeri sopra i picchi
    distanze = np.diff(picchi)
    soglia_mezzo_bit = campioni_per_bit * 3 // 4
    i = 0
    offset_verticale = 0.0125 * max(np.abs(correlazione))  # Offset dimezzato ulteriormente
    while i < len(distanze):
        if distanze[i] < soglia_mezzo_bit:
            if i + 1 < len(distanze) and distanze[i + 1] < soglia_mezzo_bit:
                # Bit 0: primo picco = 0 (nero), secondo picco = 2 (verde)
                ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '0', 
                         color='black', ha='center', va='bottom', weight='bold')
                ax2.text(picchi[i + 1], correlazione[picchi[i + 1]] + offset_verticale, '2', 
                         color='green', ha='center', va='bottom', weight='bold')
                i += 2
            else:
                # Transizione non valida: 2 (verde)
                ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '2', 
                         color='green', ha='center', va='bottom', weight='bold')
                i += 1
        else:
            # Bit 1: 1 (blu)
            ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '1', 
                     color='blue', ha='center', va='bottom', weight='bold')
            i += 1
        if i < len(distanze) and i >= len(bits):
            # Fine sequenza o errore: 3 (rosso)
            ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '3', 
                     color='red', ha='center', va='bottom', weight='bold')
            i += 1

    ax2.set_title('Correlazione e Picchi con Bit (0=Nero, 1=Blu, 2=Verde, 3=Rosso)')
    ax2.legend()

    # Aggiorna la figura
    fig.canvas.draw_idle()

    # Visualizzazione dei bit nella prima finestra
    bits_text.delete(1.0, tk.END)
    bits_text.insert(tk.END, "Sequenza di bit decodificata:\n")
    bits_text.insert(tk.END, f"{bits}\n")

    # Visualizzazione dei byte e CRC nella seconda finestra
    risultato_text.delete(1.0, tk.END)
    if bytes_decodificati is not None:
        risultato_text.insert(tk.END, "Byte decodificati:\n")
        for byte in bytes_decodificati:
            risultato_text.insert(tk.END, f"{byte:08b}\n")
        risultato_text.insert(tk.END, f"\nCRC Ricevuto: {crc_ricevuto:04X}\n")
        risultato_text.insert(tk.END, f"CRC Calcolato: {crc_calcolato:04X}\n")
        risultato_text.insert(tk.END, f"CRC OK: {crc_ok}\n")

        if crc_ok:
            country_code = (bytes_decodificati[5] << 2) | (bytes_decodificati[4] >> 6)
            device_code = (bytes_decodificati[4] & 0x3F) << 32 | (bytes_decodificati[3] << 24) | \
                          (bytes_decodificati[2] << 16) | (bytes_decodificati[1] << 8) | bytes_decodificati[0]
            risultato_text.insert(tk.END, f"\nCountry Code: {country_code}\n")
            risultato_text.insert(tk.END, f"Device Code: {device_code}\n")
    else:
        risultato_text.insert(tk.END, "Nessuna sequenza valida trovata.\n")

    status_label.config(text="Stato: Visualizzazione e decodifica completate")

# Funzione per chiamare l'analisi ESP32
def analizza_file():
    """Chiama la funzione di analisi a buffer scorrevole da analisiESP32.py."""
    percorso_file = percorso_file_var.get()
    if not percorso_file or not os.path.exists(percorso_file):
        status_label.config(text="Errore: Nessun file selezionato o file non trovato")
        return
    status_label.config(text="Stato: Analisi ESP32 in corso...")
    analisiESP32.analizza_con_buffer_scorrevole(percorso_file, status_label)
    status_label.config(text="Stato: Analisi ESP32 completata")

# Funzione per sincronizzare gli assi
def sincronizza_assi(event):
    """Sincronizza i limiti orizzontali tra i due grafici."""
    if event.inaxes == ax1:
        ax2.set_xlim(ax1.get_xlim())
    elif event.inaxes == ax2:
        ax1.set_xlim(ax2.get_xlim())
    fig.canvas.draw_idle()

# Creazione della GUI
window = tk.Tk()
window.title("Acquisizione Segnale ESP32")

# Variabile per il percorso del file
percorso_file_var = tk.StringVar(value="")

# Variabile per il checkbox della media scorrevole
media_scorrevole_var = tk.BooleanVar(value=True)  # Default: abilitata

# Layout della GUI
tk.Label(window, text="File:").grid(row=0, column=0, padx=5, pady=5)
tk.Entry(window, textvariable=percorso_file_var, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(window, text="Scegli File", command=seleziona_file).grid(row=0, column=2, padx=5, pady=5)

tk.Button(window, text="Acquisisci da ESP32", command=avvia_acquisizione).grid(row=1, column=1, padx=5, pady=5)
tk.Button(window, text="Visualizza", command=visualizza_file).grid(row=2, column=1, padx=5, pady=5)
tk.Button(window, text="Analizza", command=analizza_file).grid(row=3, column=1, padx=5, pady=5)

# Checkbox per abilitare/disabilitare la media scorrevole
tk.Checkbutton(window, text="Abilita Media Scorrevole", variable=media_scorrevole_var).grid(row=4, column=1, padx=5, pady=5)

status_label = tk.Label(window, text="Stato: Inattivo")
status_label.grid(row=5, column=1, padx=5, pady=5)

# Area di testo per i bit
tk.Label(window, text="Bit Decodificati:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
bits_text = tk.Text(window, height=5, width=60)
bits_text.grid(row=7, column=0, columnspan=3, padx=5, pady=5)

# Area di testo per i byte e CRC
tk.Label(window, text="Byte e CRC:").grid(row=8, column=0, padx=5, pady=5, sticky="w")
risultato_text = tk.Text(window, height=20, width=60)
risultato_text.grid(row=9, column=0, columnspan=3, padx=5, pady=5)

# Creazione della figura Matplotlib
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9))
plt.tight_layout()
plt.show(block=False)

# Connessione della callback per la sincronizzazione degli assi
fig.canvas.mpl_connect('motion_notify_event', sincronizza_assi)

# Avvio della GUI
window.mainloop()