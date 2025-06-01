import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import struct

def media_correlazione_32(segnale, larghezza_finestra=8, lunghezza_correlazione=32, log_widget=None):
    # Codice invariato (lo stesso della versione precedente)
    # ... (includi tutto il codice originale di media_correlazione_32)
    N = len(segnale)
    segnale_32 = np.array(segnale, dtype=np.int32)
    segnale_filtrato32 = np.zeros(N, dtype=np.int32)
    correlazione32 = np.zeros(N, dtype=np.int32)
    picchi32 = []
    distanze32 = []
    bits32 = []
    soglia_mezzo_bit = 24
    stato_decodifica = 0
    contatore_zeri = 0
    contatore_bytes = 0
    contatore_bits = 0
    stato_decobytes = 0
    ultima_distanza = 0
    newbit = 0
    duebit = False
    newpeak = False
    numbit = 0
    bytes32 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    def log_message(message):
        if log_widget:
            log_widget.insert(tk.END, message + "\n")
            log_widget.see(tk.END)
        else:
            print(message)

    for i in range(28):
        segnale_filtrato32[i] = 0
    for i in range(16):
        correlazione32[i] = 0

    i = 32
    if i < N and i + 3 < N:
        somma_media = np.sum(segnale_32[i-4:i+4], dtype=np.int32)
        segnale_filtrato32[i] = somma_media // larghezza_finestra

    if i >= lunghezza_correlazione:
        correlazione32[16] = 0
        for j in range(16):
            correlazione32[16] += segnale_filtrato32[j]
        for j in range(16, 32):
            correlazione32[16] -= segnale_filtrato32[j]

    max_i = max_i8 = min_i = min_i8 = 0
    stato = 1
    if N > 24:
        max_i = min_i = correlazione32[16]
        max_i8 = min_i8 = correlazione32[8]

    for i in range(33, N-4):
        segnale_filtrato32[i] = segnale_filtrato32[i-1] - (segnale_32[i-4] // larghezza_finestra) + (segnale_32[i+3] // larghezza_finestra)
        correlazione32[i-16] = correlazione32[i-17] - segnale_filtrato32[i-32] + 2 * segnale_filtrato32[i-16] - segnale_filtrato32[i]

        newbit = 2
        numbit = 0
        newpeak = False

        if stato == 1:
            max_i = max(correlazione32[i-16], max_i)
            max_i8 = max(correlazione32[i-24], max_i8)
            if max_i == max_i8:
                picchi32.append(i-24)
                stato = -1
                min_i = correlazione32[i-16]
                min_i8 = correlazione32[i-24]
                newpeak = True
        else:
            min_i = min(correlazione32[i-16], min_i)
            min_i8 = min(correlazione32[i-24], min_i8)
            if min_i == min_i8:
                picchi32.append(i-24)
                stato = 1
                max_i = correlazione32[i-16]
                max_i8 = correlazione32[i-24]
                newpeak = True

        if len(picchi32) > 1 and newpeak:
            nuova_distanza = picchi32[-1] - picchi32[-2]
            distanze32.append(nuova_distanza)
            if stato_decodifica == 0:
                if nuova_distanza >= soglia_mezzo_bit:
                    bits32.append((1, i-24))
                    newbit = 1
                    numbit = 1
                else:
                    ultima_distanza = nuova_distanza
                    stato_decodifica = 1
            elif stato_decodifica == 1:
                if nuova_distanza < soglia_mezzo_bit:
                    bits32.append((0, i-24))
                    newbit = 0
                    numbit = 1
                else:
                    bits32.append((1, i-24-nuova_distanza))
                    bits32.append((1, i-24))
                    newbit = 1
                    numbit = 2
                stato_decodifica = 0

        while numbit > 0:
            match stato_decobytes:
                case 0:
                    if newbit == 0:
                        contatore_zeri += 1
                    else:
                        if contatore_zeri >= 10:
                            stato_decobytes = 1
                            contatore_bytes = 0
                            contatore_bits = 0
                            bytes32 = [0] * 10
                            log_message(f"Sequenza sync at: {i}")
                        contatore_zeri = 0

                case 1:
                    if contatore_bits < 8:
                        bytes32[contatore_bytes] >>= 1
                        if newbit == 1:
                            bytes32[contatore_bytes] |= 0x80
                        contatore_bits += 1
                    else:
                        if newbit == 1:
                            contatore_bytes += 1
                            contatore_bits = 0
                            if contatore_bytes >= 10:
                                hex_bytes = [f"{byte:02X}" for byte in bytes32]
                                log_message(f"Byte estratti: [{', '.join(hex_bytes)}]")
                                contatore_zeri = 0
                                contatore_bytes = 0
                                stato_decobytes = 0

                                crc = 0x0
                                polynomial = 0x1021
                                for byte in bytes32:
                                    b = byte
                                    for j in range(8):
                                        bit = ((b >> j) & 1) == 1
                                        c15 = ((crc >> 15) & 1) == 1
                                        crc <<= 1
                                        if c15 ^ bit:
                                            crc ^= polynomial
                                    crc &= 0xffff
                                if crc == 0:
                                    log_message("CRC OK")
                                    country_code = (bytes32[5] << 2) | (bytes32[4] >> 6)
                                    device_code = (bytes32[4] & 0x3F) << 32 | (bytes32[3] << 24) | \
                                                  (bytes32[2] << 16) | (bytes32[1] << 8) | bytes32[0]
                                    log_message(f"Country Code: {country_code}")
                                    log_message(f"Device Code: {device_code}")
                                else:
                                    log_message(f"CRC: {crc:04X}")
                        else:
                            log_message(f"Perso sync at: {i}")
                            contatore_zeri = 0
                            contatore_bits = 0
                            stato_decobytes = 0
            numbit -= 1

    correlazione32[:64] = 0
    return segnale_filtrato32, correlazione32, picchi32, distanze32, bits32, bytes32

def analizza_con_buffer_scorrevole(percorso_file, status_label):
    print("Debug: Inizio analizza_con_buffer_scorrevole...")
    periodo_campionamento = 1 / 134.2e3 * 1e6
    durata_bit = 1 / (134.2e3 / 32) * 1e6
    campioni_per_bit = int(durata_bit / periodo_campionamento)

    with open(percorso_file, "rb") as f:
        dati = f.read()
    segnale_32 = np.array(struct.unpack("<" + "h" * (len(dati) // 2), dati), dtype=np.int32)
    print(f"Debug: Segnale letto, lunghezza: {len(segnale_32)}")

    segnale_filtrato32, correlazione32, picchi32, distanze32, bits32, bytes32 = media_correlazione_32(segnale_32, log_widget=None)
    status_label.config(text="Stato: Analisi ESP32 - Media, correlazione e decodifica completate")
    print(f"Debug: Segnale filtrato restituito, lunghezza: {len(segnale_filtrato32)}")

    visualizza_analisi_esp32(segnale_32, correlazione32, picchi32, distanze32, bits32, bytes32, campioni_per_bit)

    print("Debug: Fine analizza_con_buffer_scorrevole")
    return segnale_filtrato32



# Variabile globale per memorizzare ax1_32
_ax1_32 = None

def visualizza_analisi_esp32(segnale_32, correlazione32, picchi32, distanze32, bits32, bytes32, campioni_per_bit):
    global _ax1_32
    print("Debug: Inizio visualizza_analisi_esp32...")
    window32 = tk.Toplevel()
    window32.title("Analisi ESP32")

    frame = tk.Frame(window32)
    frame.pack(fill=tk.BOTH, expand=True)

    log_widget = tk.Text(frame, height=10, width=80)
    log_widget.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

    segnale_filtrato32, correlazione32, picchi32, distanze32, bits32, bytes32 = media_correlazione_32(segnale_32, log_widget=log_widget)

    fig32, (ax1_32, ax2_32) = plt.subplots(2, 1, figsize=(12, 9))
    plt.tight_layout()

    ax1_32.plot(segnale_32, label="Segnale (32-bit)", color='blue')
    for i in range(0, len(segnale_32), campioni_per_bit):
        ax1_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax1_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax1_32.set_title('Segnale di Ingresso (ESP32)')
    ax1_32.legend()

    ax2_32.plot(correlazione32, label='Correlazione (32-bit)', color='green')
    ax2_32.plot(picchi32, correlazione32[picchi32], "x", color='darkorange', label='Picchi', 
                markersize=10, markeredgewidth=2)
    bit0_posizioni = [pos for bit, pos in bits32 if bit == 0]
    bit0_valori = [correlazione32[pos] for bit, pos in bits32 if bit == 0]
    bit1_posizioni = [pos for bit, pos in bits32 if bit == 1]
    bit1_valori = [correlazione32[pos] for bit, pos in bits32 if bit == 1]
    ax2_32.plot(bit0_posizioni, bit0_valori, "o", color='blue', label='Bit 0', 
                markersize=8, markeredgewidth=1.5)
    ax2_32.plot(bit1_posizioni, bit1_valori, "o", color='red', label='Bit 1', 
                markersize=8, markeredgewidth=1.5)
    for i in range(0, len(correlazione32), campioni_per_bit):
        ax2_32.axvline(i, color='black', linestyle='-', linewidth=0.8)
        ax2_32.axvline(i + campioni_per_bit // 2, color='gray', linestyle='--', linewidth=0.5)
    ax2_32.set_title('Correlazione (ESP32) con Picchi e Bit')
    ax2_32.legend()

    def sincronizza_assi_32(event):
        if event.inaxes == ax1_32:
            ax2_32.set_xlim(ax1_32.get_xlim())                                                                                    
        elif event.inaxes == ax2_32:
            ax1_32.set_xlim(ax2_32.get_xlim())
        fig32.canvas.draw_idle()

    fig32.canvas.mpl_connect('motion_notify_event', sincronizza_assi_32)
    
    canvas = FigureCanvasTkAgg(fig32, master=frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    _ax1_32 = ax1_32  # Memorizza ax1_32
    
    print("Debug: Fine visualizza_analisi_esp32")

def get_ax1_32():
    """Restituisce l'asse ax1_32 dell'analisi ESP32."""
    return _ax1_32