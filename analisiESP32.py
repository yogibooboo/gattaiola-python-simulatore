import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
import struct

def media_correlazione_32(segnale, larghezza_finestra=8, lunghezza_correlazione=32):
    N = len(segnale)
    segnale_32 = np.array(segnale, dtype=np.int32)
    segnale_filtrato32 = np.zeros(N, dtype=np.int32)
    correlazione32 = np.zeros(N, dtype=np.int32)
    picchi32 = []
    distanze32 = []
    bits32 = []
    soglia_mezzo_bit = 24
    stato_decodifica = 0
    ultima_distanza = 0

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

        if stato == 1:
            max_i = max(correlazione32[i-16], max_i)
            max_i8 = max(correlazione32[i-24], max_i8)
            if max_i == max_i8:
                picchi32.append(i-24)
                if len(picchi32) > 1:
                    nuova_distanza = picchi32[-1] - picchi32[-2]
                    distanze32.append(nuova_distanza)
                    if stato_decodifica == 0:
                        if nuova_distanza >= soglia_mezzo_bit:
                            bits32.append((1, i-24))
                        else:
                            ultima_distanza = nuova_distanza
                            stato_decodifica = 1
                    elif stato_decodifica == 1:
                        if nuova_distanza < soglia_mezzo_bit:
                            bits32.append((0, i-24))
                        stato_decodifica = 0
                stato = -1
                min_i = correlazione32[i-16]
                min_i8 = correlazione32[i-24]
        else:
            min_i = min(correlazione32[i-16], min_i)
            min_i8 = min(correlazione32[i-24], min_i8)
            if min_i == min_i8:
                picchi32.append(i-24)
                if len(picchi32) > 1:
                    nuova_distanza = picchi32[-1] - picchi32[-2]
                    distanze32.append(nuova_distanza)
                    if stato_decodifica == 0:
                        if nuova_distanza >= soglia_mezzo_bit:
                            bits32.append((1, i-24))
                        else:
                            ultima_distanza = nuova_distanza
                            stato_decodifica = 1
                    elif stato_decodifica == 1:
                        if nuova_distanza < soglia_mezzo_bit:
                            bits32.append((0, i-24))
                        stato_decodifica = 0
                stato = 1
                max_i = correlazione32[i-16]
                max_i8 = correlazione32[i-24]

    correlazione32[:64] = 0
    return segnale_filtrato32, correlazione32, picchi32, distanze32, bits32

def analizza_con_buffer_scorrevole(percorso_file, status_label):
    periodo_campionamento = 1 / 134.2e3 * 1e6
    durata_bit = 1 / (134.2e3 / 32) * 1e6
    campioni_per_bit = int(durata_bit / periodo_campionamento)

    with open(percorso_file, "rb") as f:
        dati = f.read()
    segnale_32 = np.array(struct.unpack("<" + "h" * (len(dati) // 2), dati), dtype=np.int32)

    segnale_filtrato32, correlazione32, picchi32, distanze32, bits32 = media_correlazione_32(segnale_32)
    status_label.config(text="Stato: Analisi ESP32 - Media, correlazione e decodifica completate")

    print("Picchi:", picchi32)
    print("Distanze:", distanze32)
    print("Bit decodificati (bit, posizione):", bits32)

    visualizza_analisi_esp32(segnale_32, correlazione32, picchi32, bits32, campioni_per_bit)

    return []

def visualizza_analisi_esp32(segnale_32, correlazione32, picchi32, bits32, campioni_per_bit):
    window32 = tk.Tk()
    window32.title("Analisi ESP32")

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
    # Separa bit 0 e bit 1
    bit0_posizioni = [pos for bit, pos in bits32 if bit == 0]
    bit0_valori = [correlazione32[pos] for bit, pos in bits32 if bit == 0]
    bit1_posizioni = [pos for bit, pos in bits32 if bit == 1]
    bit1_valori = [correlazione32[pos] for bit, pos in bits32 if bit == 1]
    # Plot bit 0 (cerchi blu)
    ax2_32.plot(bit0_posizioni, bit0_valori, "o", color='blue', label='Bit 0', 
                markersize=8, markeredgewidth=1.5)
    # Plot bit 1 (cerchi rossi)
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

    plt.show(block=False)
    window32.mainloop()