import tkinter as tk
from tkinter import filedialog
import asyncio
import websockets
import os
import struct
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import analisiESP32
import correlazione

def genera_nome_file(base_path="D:\\downloads", nome_base="adc_buffer", estensione=".bin"):
    file_path = os.path.join(base_path, f"{nome_base}{estensione}")
    indice = 1
    while os.path.exists(file_path):
        file_path = os.path.join(base_path, f"{nome_base} ({indice}){estensione}")
        indice += 1
    return file_path

async def acquisisci_da_esp32(status_label, percorso_file_var):
    uri = "ws://192.168.1.105/ws"
    try:
        status_label.config(text="Stato: Connessione in corso...")
        async with websockets.connect(uri) as websocket:
            status_label.config(text="Stato: Connesso")
            await websocket.send("get_buffer")
            status_label.config(text="Stato: Download in corso...")
            while True:
                try:
                    blob = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    if isinstance(blob, str):
                        status_label.config(text=f"Stato: Ignorato messaggio testuale: {blob[:50]}...")
                        continue
                    download_path = genera_nome_file()
                    with open(download_path, "wb") as f:
                        f.write(blob)
                    percorso_file_var.set(download_path)
                    status_label.config(text=f"Stato: Buffer ricevuto e salvato in {download_path}")
                    break
                except asyncio.TimeoutError:
                    status_label.config(text="Errore: Timeout in attesa del buffer binario")
                    return
                except websockets.exceptions.ConnectionClosed:
                    status_label.config(text="Errore: Connessione chiusa inaspettatamente")
                    return
    except Exception as e:
        status_label.config(text=f"Errore: {e}")

def avvia_acquisizione(status_label, percorso_file_var):
    asyncio.run(acquisisci_da_esp32(status_label, percorso_file_var))

def seleziona_file(percorso_file_var, status_label):
    percorso_file = filedialog.askopenfilename(filetypes=[("File BIN", "*.bin")])
    if percorso_file:
        percorso_file_var.set(percorso_file)
        status_label.config(text=f"Stato: File selezionato: {percorso_file}")

def visualizza_file(percorso_file_var, status_label, media_scorrevole_var, ax1, ax2, fig, bits_text, risultato_text):
    percorso_file = percorso_file_var.get()
    if not percorso_file or not os.path.exists(percorso_file):
        status_label.config(text="Errore: Nessun file selezionato o file non trovato")
        return

    with open(percorso_file, "rb") as f:
        data = f.read()
    segnale_normalizzato = np.array(struct.unpack("<" + "h" * (len(data) // 2), data))

    periodo_campionamento = 1 / 134.2e3 * 1e6
    durata_bit = 1 / (134.2e3 / 32) * 1e6
    campioni_per_bit = int(durata_bit / periodo_campionamento)
    larghezza_finestra = int((durata_bit / 4) / periodo_campionamento)

    if media_scorrevole_var.get():
        print("Debug: Media scorrevole abilitata")
        finestra = np.ones(larghezza_finestra) / larghezza_finestra
        segnale_filtrato = np.convolve(segnale_normalizzato, finestra, mode='same')
    else:
        print("Debug: Media scorrevole non abilitata")
        segnale_filtrato = segnale_normalizzato
    segnale_filtrato = np.nan_to_num(segnale_filtrato)

    forma_onda_ideale = np.concatenate([np.ones(campioni_per_bit // 2), -np.ones(campioni_per_bit // 2)])
    correlazione = np.correlate(segnale_filtrato, forma_onda_ideale, mode='same')
    picchi, _ = find_peaks(np.abs(correlazione), prominence=0.5)

    distanze = np.diff(picchi)
    soglia_mezzo_bit = campioni_per_bit * 3 // 4
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

    for i in range(len(bits) - 9):
        if all(bit == 0 for bit in bits[i:i + 10]):
            indice_partenza = i + 10
            break
    else:
        bytes_decodificati = None

    if 'indice_partenza' in locals():
        bytes_decodificati = []
        for i in range(10):
            indice_byte = indice_partenza + i * 9
            if indice_byte + 9 > len(bits):
                bytes_decodificati = None
                break
            if bits[indice_byte] != 1:
                bytes_decodificati = None
                break
            byte = 0
            for j in range(8):
                byte |= bits[indice_byte + 1 + j] << j
            bytes_decodificati.append(byte)

    crc_ok = False
    if bytes_decodificati:
        dati = bytes_decodificati[:-2]
        crc_ricevuto = (bytes_decodificati[-1] << 8) | bytes_decodificati[-2]
        crc_calcolato = 0x0
        polynomial = 0x1021
        for byte in dati:
            b = byte
            for i in range(8):
                bit = ((b >> i) & 1) == 1
                c15 = ((crc_calcolato >> 15) & 1) == 1
                crc_calcolato <<= 1
                if c15 ^ bit:
                    crc_calcolato ^= polynomial
            crc_calcolato &= 0xffff
        crc_reversed = 0
        for i in range(0, 16):
            if (crc_calcolato >> i) & 1:
                crc_reversed |= 1 << (15 - i)
        crc_ok = crc_ricevuto == crc_reversed
        crc_calcolato = crc_reversed

    ax1.clear()
    ax2.clear()

    ax1.plot(segnale_normalizzato, label=f"Segnale Normalizzato\nCampioni/bit: {campioni_per_bit}")
    for i in range(0, len(segnale_normalizzato), campioni_per_bit):
        ax1.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax1.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax1.set_title('Segnale Normalizzato')
    ax1.legend()

    ax2.plot(correlazione, label='Correlazione', color='green')
    ax2.plot(picchi, correlazione[picchi], "x", label='Picchi')
    for i in range(0, len(correlazione), campioni_per_bit):
        ax2.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax2.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)

    i = 0
    offset_verticale = 0.0125 * max(np.abs(correlazione))
    while i < len(distanze):
        if distanze[i] < soglia_mezzo_bit:
            if i + 1 < len(distanze) and distanze[i + 1] < soglia_mezzo_bit:
                ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '0', color='black', ha='center', va='bottom', weight='bold')
                i += 2
            else:
                ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '2', color='green', ha='center', va='bottom', weight='bold')
                i += 1
        else:
            ax2.text(picchi[i], correlazione[picchi[i]] + offset_verticale, '1', color='blue', ha='center', va='bottom', weight='bold')
            i += 1

    ax2.set_title('Correlazione e Picchi con Bit (0=Nero, 1=Blu, 2=Verde)')
    ax2.legend()

    fig.canvas.draw_idle()

    bits_text.delete(1.0, tk.END)
    bits_text.insert(tk.END, "Sequenza di bit decodificata:\n")
    bits_text.insert(tk.END, f"{bits}\n")

    risultato_text.delete(1.0, tk.END)
    if bytes_decodificati:
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

def analizza_file(percorso_file_var, status_label, bits_text, somma_offset_4096=False):
    print("Debug: Inizio analizza_file...")
    percorso_file = percorso_file_var.get()
    print(f"Debug: Percorso file: '{percorso_file}'")
    if not percorso_file or not os.path.exists(percorso_file):
        print("Debug: Errore: Nessun file selezionato o file non trovato")
        status_label.config(text="Errore: Nessun file selezionato o file non trovato")
        return None
    status_label.config(text="Stato: Analisi ESP32 in corso...")
    bits_text.delete(1.0, tk.END)
    try:
        segnale_filtrato = analisiESP32.analizza_con_buffer_scorrevole(percorso_file, status_label, lambda msg: bits_text.insert(tk.END, msg + "\n"), somma_offset_4096=somma_offset_4096)
        print(f"Debug: analizza_con_buffer_scorrevole completata, segnale_filtrato: {segnale_filtrato is not None}, lunghezza: {len(segnale_filtrato) if segnale_filtrato is not None else 'None'}")
        status_label.config(text="Stato: Analisi ESP32 completata")
        return segnale_filtrato
    except Exception as e:
        print(f"Debug: Errore in analizza_file: {e}")
        status_label.config(text=f"Errore: Analisi ESP32 fallita: {e}")
        bits_text.insert(tk.END, f"Errore: {e}\n")
        return None

def esegui_correlazione(percorso_file_var, status_label, risultato_text, media_scorrevole_var):
    print("Debug: Inizio esecuzione correlazione...")
    try:
        print("Debug: Chiamo analizza_file...")
        segnale_filtrato = analizza_file(percorso_file_var, status_label, bits_text)
        print(f"Debug: Analisi completata, segnale_filtrato: {segnale_filtrato is not None}, lunghezza: {len(segnale_filtrato) if segnale_filtrato is not None else 'None'}")
        print("Debug: Procedo con correlazione...")
        ax1_32 = analisiESP32.get_ax1_32()
        if ax1_32 is None:
            status_label.config(text="Errore: Finestra di analisi ESP32 non disponibile")
            risultato_text.insert(tk.END, "Errore: Finestra di analisi ESP32 non disponibile\n")
            return
        try:
            print(f"Debug: Accesso a correlazione.BYTES_NOTI: {correlazione.BYTES_NOTI}")
        except AttributeError as e:
            print(f"Debug: Errore: {e}")
            status_label.config(text="Errore: BYTES_NOTI non trovato in correlazione")
            risultato_text.insert(tk.END, f"Errore: {e}\n")
            return
        print("Debug: Chiamo correlazione_con_sequenza_nota...")
        correlazione.correlazione_con_sequenza_nota(
            percorso_file_var.get(),
            correlazione.BYTES_NOTI,
            status_label,
            ax1_32,
            risultato_text,
            segnale_filtrato,
            media_scorrevole_var
        )
        print("Debug: Correlazione completata")
    except Exception as e:
        print(f"Debug: Errore in esegui_correlazione: {e}")
        status_label.config(text=f"Errore: Correlazione fallita: {e}")
        risultato_text.insert(tk.END, f"Errore: {e}\n")

def sincronizza_assi(ax1, ax2, fig):
    def handler(event):
        if event.inaxes == ax1:
            ax2.set_xlim(ax1.get_xlim())
        elif event.inaxes == ax2:
            ax1.set_xlim(ax2.get_xlim())
        fig.canvas.draw_idle()
    return handler

window = tk.Tk()
window.title("Acquisizione Segnale ESP32")

percorso_file_var = tk.StringVar(value="")
media_scorrevole_var = tk.BooleanVar(value=True)

tk.Label(window, text="File:").grid(row=0, column=0, padx=5, pady=5)
tk.Entry(window, textvariable=percorso_file_var, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(window, text="Scegli File", command=lambda: seleziona_file(percorso_file_var, status_label)).grid(row=0, column=2, padx=5, pady=5)

tk.Button(window, text="Acquisisci da ESP32", command=lambda: avvia_acquisizione(status_label, percorso_file_var)).grid(row=1, column=1, padx=5, pady=5)
tk.Button(window, text="Visualizza", command=lambda: visualizza_file(percorso_file_var, status_label, media_scorrevole_var, ax1, ax2, fig, bits_text, risultato_text)).grid(row=2, column=1, padx=5, pady=5)
tk.Button(window, text="Analizza", command=lambda: analizza_file(percorso_file_var, status_label, bits_text)).grid(row=3, column=1, padx=5, pady=5)
tk.Button(window, text="ANA2", command=lambda: analizza_file(percorso_file_var, status_label, bits_text, somma_offset_4096=True)).grid(row=3, column=2, padx=5, pady=5)
tk.Button(window, text="Correlazione", command=lambda: esegui_correlazione(percorso_file_var, status_label, risultato_text, media_scorrevole_var)).grid(row=4, column=1, padx=5, pady=5)

tk.Checkbutton(window, text="Abilita Media Scorrevole", variable=media_scorrevole_var).grid(row=5, column=1, padx=5, pady=5)

status_label = tk.Label(window, text="Stato: Inattivo")
status_label.grid(row=6, column=1, padx=5, pady=5)

tk.Label(window, text="Risultato Decodifica:").grid(row=7, column=0, padx=5, pady=5, sticky="w")
bits_text = tk.Text(window, height=10, width=60)
bits_text.grid(row=8, column=0, columnspan=3, padx=5, pady=5)

tk.Label(window, text="Byte e CRC:").grid(row=9, column=0, padx=5, pady=5, sticky="w")
risultato_text = tk.Text(window, height=20, width=60)
risultato_text.grid(row=10, column=0, columnspan=3, padx=5, pady=5)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
plt.tight_layout(pad=2.0)

fig.canvas.mpl_connect('motion_notify_event', sincronizza_assi(ax1, ax2, fig))

window.mainloop()